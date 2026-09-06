"""
VARUNA Backend — upstream service client.

Async HTTP client for calling upstream services:
- Person 1's Graph Fusion Engine (/model, /observations, /fused)
- Person 2's Drift Memory Engine (/alerts) — Day 3
- Person 4's Model Pipeline — Day 3
- Person 6's Observation Pipeline — Day 3

Features:
- Connection pooling via httpx.AsyncClient
- Retry with exponential backoff
- Response caching with configurable TTL
- Graceful mock-data fallback when upstream is unreachable (Day 1/2)
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any

import httpx

from ..config import Settings, get_settings

logger = logging.getLogger("varuna.upstream")


class _CacheEntry:
    """A single cached response with expiry."""

    __slots__ = ("data", "expires_at")

    def __init__(self, data: Any, ttl: float) -> None:
        self.data = data
        self.expires_at = time.monotonic() + ttl

    @property
    def expired(self) -> bool:
        return time.monotonic() >= self.expires_at


class UpstreamClient:
    """
    Async HTTP client for upstream VARUNA services.

    Usage::

        client = UpstreamClient(settings)
        await client.start()
        data = await client.get_json("http://localhost:8001/model")
        await client.stop()
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._cfg = settings or get_settings()
        self._client: httpx.AsyncClient | None = None
        self._cache: dict[str, _CacheEntry] = {}

    async def start(self) -> None:
        """Create the connection-pooled HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._cfg.upstream_timeout_s),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
            logger.info("Upstream HTTP client started")

    async def stop(self) -> None:
        """Close the HTTP client and clear cache."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._cache.clear()
        logger.info("Upstream HTTP client stopped")

    def _cache_key(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()

    def _get_cached(self, url: str) -> Any | None:
        key = self._cache_key(url)
        entry = self._cache.get(key)
        if entry and not entry.expired:
            logger.debug("Cache hit: %s", url)
            return entry.data
        if entry:
            del self._cache[key]
        return None

    def _set_cached(self, url: str, data: Any) -> None:
        if self._cfg.upstream_cache_ttl_s > 0:
            key = self._cache_key(url)
            self._cache[key] = _CacheEntry(data, self._cfg.upstream_cache_ttl_s)

    async def get_json(self, url: str, *, use_cache: bool = True) -> Any:
        """
        GET a URL and return parsed JSON.

        Retries on transient failures with exponential backoff.
        Responses are cached for ``upstream_cache_ttl_s`` seconds.
        """
        if use_cache:
            cached = self._get_cached(url)
            if cached is not None:
                return cached

        if not self._client:
            await self.start()

        last_exc: Exception | None = None
        for attempt in range(self._cfg.upstream_max_retries + 1):
            try:
                resp = await self._client.get(url)  # type: ignore[union-attr]
                resp.raise_for_status()
                data = resp.json()
                self._set_cached(url, data)
                return data
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                if attempt < self._cfg.upstream_max_retries:
                    wait = 0.5 * (2 ** attempt)
                    logger.warning(
                        "Upstream %s attempt %d failed (%s), retrying in %.1fs",
                        url, attempt + 1, exc, wait,
                    )
                    await asyncio.sleep(wait)

        logger.error("Upstream %s failed after %d attempts", url, self._cfg.upstream_max_retries + 1)
        raise last_exc  # type: ignore[misc]

    # ── convenience methods for specific upstream endpoints ──────────

    async def get_model(self, *, use_mock_fallback: bool = True) -> dict:
        """Fetch /model from graph fusion engine; fall back to mock if down."""
        from . import mock_data  # local import avoids circular at module level
        url = f"{self._cfg.graph_fusion_url}/model"
        try:
            return await self.get_json(url)
        except Exception as exc:
            if not use_mock_fallback:
                raise
            logger.debug("Upstream /model unreachable (%s) — using mock data", exc)
            return mock_data.generate_model_snapshot()

    async def get_observations(self, *, use_mock_fallback: bool = True) -> dict:
        """Fetch /observations from graph fusion engine; fall back to mock if down."""
        from . import mock_data
        url = f"{self._cfg.graph_fusion_url}/observations"
        try:
            return await self.get_json(url)
        except Exception as exc:
            if not use_mock_fallback:
                raise
            logger.debug("Upstream /observations unreachable (%s) — using mock data", exc)
            return mock_data.generate_observation_snapshot()

    async def get_fused(self, engine: str = "auto", *, use_mock_fallback: bool = True) -> dict:
        """Fetch /fused from graph fusion engine; fall back to mock if down."""
        from . import mock_data
        url = f"{self._cfg.graph_fusion_url}/fused?engine={engine}"
        try:
            return await self.get_json(url)
        except Exception as exc:
            if not use_mock_fallback:
                raise
            logger.debug("Upstream /fused unreachable (%s) — using mock data", exc)
            return mock_data.generate_fused_snapshot(engine=engine)

    async def get_alerts(self, *, use_mock_fallback: bool = True) -> list:
        """Fetch alerts from graph fusion engine (or drift memory engine); fall back to mock."""
        from . import mock_data
        url = f"{self._cfg.graph_fusion_url}/alerts"
        try:
            return await self.get_json(url, use_cache=False)
        except Exception as exc:
            if not use_mock_fallback:
                raise
            logger.debug("Upstream /alerts unreachable (%s) — using mock data", exc)
            return mock_data.generate_alerts()

    async def get_health(self) -> dict:
        """Fetch /health from graph fusion engine."""
        url = f"{self._cfg.graph_fusion_url}/health"
        return await self.get_json(url, use_cache=False)

