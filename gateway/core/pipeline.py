"""
Middleware pipeline engine — Chain of Responsibility pattern.

The pipeline builds a nested async call chain from a list of plugins:
  plugin[0] → plugin[1] → ... → plugin[n] → handler

Each plugin calls `await next(request, ctx)` to proceed.
"""
from __future__ import annotations

import json
from typing import Any, cast
import hashlib
import logging

from fastapi import Request, Response

from gateway.config.loader import PluginConfig
from gateway.core.context import GatewayContext
from gateway.plugins.base import BasePlugin, NextFunc, PluginRegistry

logger = logging.getLogger(__name__)


class PluginCache:
    """
    Caches instantiated and configured plugin objects.
    Plugins are keyed by a hash of their configuration to ensure that
    hot-reloads or different configurations result in correct instances.
    """

    def __init__(self) -> None:
        self._cache: dict[str, BasePlugin] = {}

    def get_or_create(self, config: PluginConfig) -> BasePlugin | None:
        # Create a unique key based on plugin name and its specific configuration
        config_data = {
            "name": config.name,
            "config": config.config,
        }
        config_hash = hashlib.md5(
            json.dumps(config_data, sort_keys=True).encode("utf-8")
        ).hexdigest()

        if config_hash in self._cache:
            return self._cache[config_hash]

        # Instantiate and configure
        cls = PluginRegistry.get(config.name)
        if cls is None:
            logger.warning(f"Plugin '{config.name}' not found in registry, skipping")
            return None

        try:
            instance = cls()
            instance.configure(config.config)
            self._cache[config_hash] = instance
            logger.debug(f"Instantiated and cached plugin: {config.name} (hash={config_hash[:8]})")
            return instance
        except Exception as e:
            logger.error(f"Failed to configure plugin '{config.name}': {e}")
            return None


_global_plugin_cache = PluginCache()


# The innermost "handler" that just returns a 502 if no proxy plugin handled it
async def _default_handler(request: Request, ctx: GatewayContext) -> Response:
    return Response(
        content='{"detail":"No upstream handler resolved the request"}',
        status_code=502,
        media_type="application/json",
    )


def _build_chain(plugins: list[BasePlugin], endpoint: NextFunc) -> NextFunc:
    """
    Recursively wraps plugins around the endpoint, building the execution chain.
    Returns the outermost callable.
    """
    chain = endpoint
    for plugin in reversed(plugins):
        # Capture plugin in closure
        _plugin = plugin
        _next = chain

        async def step(
            request: Request,
            ctx: GatewayContext,
            p: BasePlugin = _plugin,
            n: NextFunc = _next,
        ) -> Response:
            return await p(request, ctx, n)

        chain = step
    return chain


class MiddlewarePipeline:
    """
    Builds and executes the middleware plugin chain for a single request.

    Usage:
        pipeline = MiddlewarePipeline(global_plugins)
        response = await pipeline.execute(request, ctx, route_plugins, proxy_handler)
    """

    def __init__(self, global_plugin_configs: list[PluginConfig]) -> None:
        self._global_configs = global_plugin_configs

    def _get_plugins(self, configs: list[PluginConfig]) -> list[BasePlugin]:
        plugins: list[BasePlugin] = []
        for cfg in configs:
            if not cfg.enabled:
                continue
            instance = _global_plugin_cache.get_or_create(cfg)
            if instance:
                plugins.append(instance)
        # Sort by order
        return sorted(plugins, key=lambda p: p.order)

    async def execute(
        self,
        request: Request,
        ctx: GatewayContext,
        route_plugin_configs: list[PluginConfig],
        proxy_handler: NextFunc,
    ) -> Response:
        """
        Execute the full plugin chain:
          global plugins → route-specific plugins → proxy_handler
        """
        global_plugins = self._get_plugins(self._global_configs)
        route_plugins = self._get_plugins(route_plugin_configs)
        all_plugins = global_plugins + route_plugins

        chain = _build_chain(all_plugins, proxy_handler)
        return await chain(request, ctx)
