"""Minimal async client for the OpenRouter API."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from .const import API_BASE

# Safety cap for /keys pagination
MAX_KEY_PAGES = 20


class OpenRouterError(Exception):
    """Generic API error."""


class OpenRouterAuthError(OpenRouterError):
    """Invalid or revoked API key."""


@dataclass
class OpenRouterData:
    """Combined data from the OpenRouter endpoints."""

    key: dict[str, Any] = field(default_factory=dict)
    # None when the key is not a management key (/credits returns 403)
    credits: dict[str, Any] | None = None
    # All API keys of the account by hash; None without a management key
    keys: dict[str, dict[str, Any]] | None = None


class OpenRouterClient:
    """Talks to openrouter.ai."""

    def __init__(self, session: aiohttp.ClientSession, api_key: str) -> None:
        self._session = session
        self._api_key = api_key

    async def _get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> tuple[int, dict[str, Any]]:
        try:
            async with asyncio.timeout(20):
                resp = await self._session.get(
                    f"{API_BASE}{path}",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    params=params,
                )
                status = resp.status
                try:
                    body = await resp.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError):
                    body = {}
        except (aiohttp.ClientError, TimeoutError) as err:
            raise OpenRouterError(f"Error communicating with OpenRouter: {err}") from err
        return status, body or {}

    async def async_get_key(self) -> dict[str, Any]:
        """Return info about the current API key."""
        status, body = await self._get("/key")
        if status == 401:
            raise OpenRouterAuthError("Invalid API key")
        if status != 200:
            raise OpenRouterError(f"Unexpected status {status} from /key: {body}")
        return body.get("data", {})

    async def async_get_credits(self) -> dict[str, Any] | None:
        """Return account credits, or None if the key lacks permission."""
        status, body = await self._get("/credits")
        if status == 401:
            raise OpenRouterAuthError("Invalid API key")
        if status == 403:
            return None
        if status != 200:
            raise OpenRouterError(f"Unexpected status {status} from /credits: {body}")
        return body.get("data", {})

    async def async_list_keys(self) -> dict[str, dict[str, Any]]:
        """Return all enabled API keys of the account (management key only)."""
        keys: dict[str, dict[str, Any]] = {}
        for _ in range(MAX_KEY_PAGES):
            status, body = await self._get("/keys", {"offset": len(keys)})
            if status == 401:
                raise OpenRouterAuthError("Invalid API key")
            if status != 200:
                raise OpenRouterError(f"Unexpected status {status} from /keys: {body}")
            page = [k for k in body.get("data", []) if k.get("hash") not in keys]
            if not page:
                break
            keys.update((k["hash"], k) for k in page if k.get("hash"))
        return keys

    async def async_get_data(self) -> OpenRouterData:
        """Fetch everything."""
        key, credits = await asyncio.gather(
            self.async_get_key(), self.async_get_credits()
        )
        keys = None
        if key.get("is_management_key") or key.get("is_provisioning_key"):
            keys = await self.async_list_keys()
        return OpenRouterData(key=key, credits=credits, keys=keys)
