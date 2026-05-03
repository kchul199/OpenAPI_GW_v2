"""
YAML-based route and gateway configuration loader.
Supports hot-reload via file watch or explicit reload call.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
import re
from typing import Any, cast

from pydantic import BaseModel, Field, field_validator
import yaml  # type: ignore[import-untyped]

import json
from gateway.core.redis import get_redis

logger = logging.getLogger(__name__)
_ENV_PLACEHOLDER_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(.*?))?\}")


# ─── Route Model ──────────────────────────────────────────────────────────────


class MatchConfig(BaseModel):
    protocol: str = "HTTP"  # HTTP | gRPC | WebSocket | MQTT
    host: str | None = None
    path: str = "/"
    methods: list[str] = Field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "PATCH"])
    headers: dict[str, str] = Field(default_factory=dict)


class UpstreamTarget(BaseModel):
    url: str
    weight: int = 100


class RetryConfig(BaseModel):
    count: int = 3
    backoff_factor: float = 0.3
    status_codes: list[int] = Field(default_factory=lambda: [502, 503, 504])


class GRPCProxyConfig(BaseModel):
    cardinality: str = "unary_unary"
    timeout: float | None = None
    wait_for_ready: bool = True
    secure: bool | None = None
    root_cert_file: str | None = None
    inject_request_id: bool = True
    drop_metadata: list[str] = Field(default_factory=lambda: ["host", ":authority"])

    @field_validator("cardinality")
    @classmethod
    def validate_cardinality(cls, value: str) -> str:
        allowed = {"unary_unary", "unary_stream", "stream_unary", "stream_stream"}
        normalized = value.lower()
        if normalized not in allowed:
            raise ValueError(f"Unsupported gRPC cardinality: {value}")
        return normalized


class WebSocketProxyConfig(BaseModel):
    connect_timeout: float = 10.0
    inject_request_id: bool = True
    forward_headers: list[str] = Field(default_factory=list)
    extra_headers: dict[str, str] = Field(default_factory=dict)


class UpstreamConfig(BaseModel):
    type: str = "REST"  # REST | gRPC | WebSocket
    targets: list[UpstreamTarget]
    timeout: float = 30.0  # seconds
    retry: RetryConfig = Field(default_factory=RetryConfig)
    load_balance: str = "round_robin"  # round_robin | random | ip_hash | least_connections
    hash_on: str = "client_ip"
    hash_key: str | None = None

    @field_validator("hash_on")
    @classmethod
    def validate_hash_on(cls, value: str) -> str:
        allowed = {"client_ip", "request_id", "header", "query_param", "path"}
        normalized = value.lower()
        if normalized not in allowed:
            raise ValueError(f"Unsupported upstream hash_on: {value}")
        return normalized


class PluginConfig(BaseModel):
    name: str
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class RouteConfig(BaseModel):
    id: str
    description: str = ""
    match: MatchConfig
    upstream: UpstreamConfig
    grpc: GRPCProxyConfig = Field(default_factory=GRPCProxyConfig)
    websocket: WebSocketProxyConfig = Field(default_factory=WebSocketProxyConfig)
    plugins: list[PluginConfig] = Field(default_factory=list)
    strip_prefix: bool = False
    preserve_host: bool = False


# ─── Gateway Config Model ─────────────────────────────────────────────────────


class GatewayConfig(BaseModel):
    name: str = "Open API Gateway"
    version: str = "1.0.0"
    global_plugins: list[PluginConfig] = Field(default_factory=list)


# ─── Loader ───────────────────────────────────────────────────────────────────


class ConfigLoader:
    """Loads and hot-reloads YAML configuration files."""

    def __init__(self, routes_path: str, gateway_path: str) -> None:
        self._routes_path = Path(routes_path)
        self._gateway_path = Path(gateway_path)
        self._routes: list[RouteConfig] = []
        self._gateway_cfg: GatewayConfig = GatewayConfig()
        self._lock = asyncio.Lock()

    @staticmethod
    def _expand_env_text(value: str, *, source: Path) -> str:
        def _replace(match: re.Match[str]) -> str:
            name = match.group(1)
            default = match.group(2)

            # 1. Try K8s Secret Mount Path (/var/run/secrets/oag/<name>)
            # This is more secure than environment variables
            secret_file = Path(f"/var/run/secrets/oag/{name.lower()}")
            if secret_file.exists():
                try:
                    return secret_file.read_text(encoding="utf-8").strip()
                except Exception as e:
                    logger.debug(f"Failed to read secret file {secret_file}: {e}")

            # 2. Try Environment Variable
            resolved = os.environ.get(name)
            if resolved is not None:
                return resolved

            # 3. Use Default
            if default is not None:
                return default

            raise ValueError(
                f"Missing required secret or environment variable '{name}' while loading {source}"
            )

        return _ENV_PLACEHOLDER_RE.sub(_replace, value)

    @classmethod
    def _expand_env_payload(cls, value: Any, *, source: Path) -> Any:
        if isinstance(value, str):
            return cls._expand_env_text(value, source=source)
        if isinstance(value, list):
            return [cls._expand_env_payload(item, source=source) for item in value]
        if isinstance(value, dict):
            return {
                key: cls._expand_env_payload(item, source=source)
                for key, item in value.items()
            }
        return value

    async def load(self) -> None:
        """Initial load of all configuration files. Prioritize Redis if available."""
        async with self._lock:
            # 1. Try Central Store (Redis)
            try:
                redis = get_redis()
                raw_routes = await redis.hgetall("oag:config:routes")
                if raw_routes:
                    self._routes = [
                        RouteConfig(**json.loads(v)) for v in raw_routes.values()
                    ]
                    raw_gw = await redis.get("oag:config:gateway")
                    if raw_gw:
                        self._gateway_cfg = GatewayConfig(**json.loads(raw_gw))
                    logger.info(f"Loaded {len(self._routes)} routes from Centralized Redis Store")
                    return
            except Exception as e:
                logger.debug(f"Centralized store not ready or empty, falling back to files: {e}")

            # 2. Fallback to Local Files
            self._routes = self._load_routes()
            self._gateway_cfg = self._load_gateway()
        logger.info(
            "Config loaded from local files",
            extra={"routes": len(self._routes), "gateway": self._gateway_cfg.name},
        )

    async def save_to_redis(self) -> None:
        """Synchronize current in-memory config to Redis for cluster-wide consistency."""
        redis = get_redis()
        pipeline = redis.pipeline()
        await pipeline.delete("oag:config:routes")
        for route in self._routes:
            await pipeline.hset(
                "oag:config:routes", route.id, route.model_dump_json(exclude_none=True)
            )
        await pipeline.set(
            "oag:config:gateway", self._gateway_cfg.model_dump_json(exclude_none=True)
        )
        await pipeline.execute()
        logger.info("Configuration synchronized to Centralized Redis Store")

    def _load_routes(self) -> list[RouteConfig]:
        if not self._routes_path.exists():
            logger.warning(f"Routes config not found: {self._routes_path}")
            return []
        raw_loaded = yaml.safe_load(self._routes_path.read_text(encoding="utf-8")) or {}
        raw = cast(dict[str, Any], self._expand_env_payload(raw_loaded, source=self._routes_path))
        return [RouteConfig(**r) for r in raw.get("routes", [])]

    def _load_gateway(self) -> GatewayConfig:
        if not self._gateway_path.exists():
            logger.warning(f"Gateway config not found: {self._gateway_path}")
            return GatewayConfig()
        raw_loaded = yaml.safe_load(self._gateway_path.read_text(encoding="utf-8")) or {}
        raw = cast(dict[str, Any], self._expand_env_payload(raw_loaded, source=self._gateway_path))
        return GatewayConfig(**raw)

    async def reload(self) -> None:
        """Hot-reload configuration without downtime."""
        async with self._lock:
            old_count = len(self._routes)
            self._routes = self._load_routes()
            self._gateway_cfg = self._load_gateway()
        logger.info(
            "Config hot-reloaded",
            extra={"routes_before": old_count, "routes_after": len(self._routes)},
        )

    def validate_route_payload(self, payload: dict[str, Any]) -> RouteConfig:
        """Validate a route payload without persisting it."""
        return RouteConfig.model_validate(payload)

    def render_routes_yaml(self, routes: list[RouteConfig]) -> str:
        document = {
            "routes": [route.model_dump(mode="python", exclude_none=True) for route in routes],
        }
        return cast(
            str,
            yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
        )

    async def save_routes(self, routes: list[RouteConfig]) -> None:
        """Persist an entire route set and update in-memory state."""
        yaml_text = self.render_routes_yaml(routes)
        async with self._lock:
            self._routes_path.write_text(yaml_text, encoding="utf-8")
            self._routes = list(routes)

    async def create_route(self, route: RouteConfig) -> None:
        """Append a new route to the persisted config."""
        async with self._lock:
            if any(existing.id == route.id for existing in self._routes):
                raise ValueError(f"Route '{route.id}' already exists")
            next_routes = [*self._routes, route]
            self._routes_path.write_text(self.render_routes_yaml(next_routes), encoding="utf-8")
            self._routes = next_routes

    async def update_route(self, current_route_id: str, route: RouteConfig) -> None:
        """Replace or rename an existing route in the persisted config."""
        async with self._lock:
            if route.id != current_route_id and any(
                existing.id == route.id for existing in self._routes
            ):
                raise ValueError(f"Route '{route.id}' already exists")

            next_routes: list[RouteConfig] = []
            found = False
            for existing in self._routes:
                if existing.id == current_route_id:
                    next_routes.append(route)
                    found = True
                else:
                    next_routes.append(existing)

            if not found:
                raise KeyError(current_route_id)

            self._routes_path.write_text(self.render_routes_yaml(next_routes), encoding="utf-8")
            self._routes = next_routes

    async def delete_route(self, route_id: str) -> None:
        """Delete a route from the persisted config."""
        async with self._lock:
            next_routes = [route for route in self._routes if route.id != route_id]
            if len(next_routes) == len(self._routes):
                raise KeyError(route_id)
            self._routes_path.write_text(self.render_routes_yaml(next_routes), encoding="utf-8")
            self._routes = next_routes

    @property
    def routes(self) -> list[RouteConfig]:
        return self._routes

    @property
    def gateway(self) -> GatewayConfig:
        return self._gateway_cfg
