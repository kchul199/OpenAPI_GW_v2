"""
Circuit Breaker Plugin.
Wraps upstream calls in a circuit breaker state machine.

Implementation: 3-state (CLOSED → OPEN → HALF_OPEN → CLOSED/OPEN)
  CLOSED    → (failure_threshold failures in window_seconds) → OPEN
  OPEN      → (recovery_timeout expires) → HALF_OPEN
  HALF_OPEN → (1 probe request success) → CLOSED
  HALF_OPEN → (1 probe request failure) → OPEN

Config keys:
  failure_threshold  (int)   : failures within window to open circuit (default: 5)
  recovery_timeout   (float) : seconds circuit stays OPEN before auto-reset (default: 30)
  window_seconds     (int)   : sliding failure counting window in seconds (default: 60)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request, Response

from gateway.core.context import GatewayContext
from gateway.core.redis import RedisClient, get_redis
from gateway.plugins.base import BasePlugin, NextFunc, PluginRegistry

logger = logging.getLogger(__name__)


@PluginRegistry.register
class CircuitBreakerPlugin(BasePlugin):
    """
    Redis-backed Distributed Circuit Breaker.
    """

    name = "circuit-breaker"
    order = 25

    def configure(self, config: dict[str, Any]) -> None:
        self._failure_threshold: int = config.get("failure_threshold", 5)
        self._recovery_timeout: float = config.get("recovery_timeout", 30.0)
        self._window_seconds: int = config.get("window_seconds", 60)

    async def __call__(self, request: Request, ctx: GatewayContext, next: NextFunc) -> Response:
        redis = get_redis()
        route_id = ctx.route_id

        open_key = f"cb:open:{route_id}"
        fails_key = f"cb:fails:{route_id}"
        half_open_key = f"cb:half_open:{route_id}"

        # 1. Check if Circuit is OPEN globally
        is_open = await redis.exists(open_key)
        if is_open:
            ctx.circuit_open = True
            ttl = await redis.ttl(open_key)
            logger.warning(
                f"Circuit OPEN globally for route={route_id}", extra={"request_id": ctx.request_id}
            )
            return Response(
                content='{"detail":"Service temporarily unavailable (circuit open)"}',
                status_code=503,
                media_type="application/json",
                headers={"Retry-After": str(max(ttl, 1))},
            )

        # 2. Check for HALF_OPEN probe
        # If the fails_key exists and is >= threshold, but open_key is gone,
        # it means we were OPEN and now we are ready to probe.
        current_fails_str = await redis.get(fails_key)
        current_fails = int(current_fails_str) if current_fails_str else 0

        is_probing = False
        if current_fails >= self._failure_threshold:
            # Try to acquire probe lock for HALF_OPEN
            # Use SET NX to ensure only one worker probes
            acquired = await redis.set(half_open_key, "1", nx=True, ex=10)
            if acquired:
                is_probing = True
                logger.info(f"Circuit HALF_OPEN: Probing route={route_id}", extra={"request_id": ctx.request_id})
            else:
                # Someone else is probing, block this request
                return Response(
                    content='{"detail":"Service recovery in progress (half-open probe)"}',
                    status_code=503,
                    media_type="application/json",
                    headers={"Retry-After": "5"},
                )

        # 3. Proceed with call
        try:
            response: Response = await next(request, ctx)
            
            if response.status_code >= 500:
                await self._handle_failure(redis, route_id, open_key, fails_key, half_open_key, is_probing)
            else:
                if is_probing:
                    # Success! Reset circuit
                    await redis.delete(fails_key)
                    await redis.delete(half_open_key)
                    logger.info(f"Circuit CLOSED: Route={route_id} recovered successfully.")
                elif current_fails > 0:
                    # Optional: gradual success threshold could be implemented here
                    pass
            return response
        except Exception:
            await self._handle_failure(redis, route_id, open_key, fails_key, half_open_key, is_probing)
            raise

    async def _handle_failure(
        self,
        redis: RedisClient,
        route_id: str,
        open_key: str,
        fails_key: str,
        half_open_key: str,
        is_probing: bool
    ) -> None:
        if is_probing:
            # Probe failed! Immediately re-open the circuit
            await redis.set(open_key, "1", ex=int(self._recovery_timeout))
            await redis.delete(half_open_key)
            logger.error(f"Circuit HALF_OPEN probe FAILED for route={route_id}. Re-opening for {self._recovery_timeout}s.")
        else:
            # Normal failure recording
            await self._record_failure(redis, route_id, open_key, fails_key)

    async def _record_failure(
        self,
        redis: RedisClient,
        route_id: str,
        open_key: str,
        fails_key: str,
    ) -> None:
        # Increment failures
        current_fails = await redis.incr(fails_key)
        # Set expiry for the failure window if it's the first failure
        if current_fails == 1:
            await redis.expire(fails_key, self._window_seconds)

        if current_fails >= self._failure_threshold:
            # Trip the circuit!
            await redis.set(open_key, "1", ex=int(self._recovery_timeout))
            logger.error(
                f"Circuit breached for route={route_id}! Opening circuit for {self._recovery_timeout}s."
            )
