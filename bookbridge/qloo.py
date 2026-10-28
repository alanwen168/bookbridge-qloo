from __future__ import annotations

import asyncio
from collections import OrderedDict, deque
from dataclasses import dataclass
from time import monotonic
from typing import Any, Protocol
from uuid import UUID

import httpx

BASE_URL = "https://hackathon.api.qloo.com"
TYPE_URNS = {"book": "urn:entity:book", "movie": "urn:entity:movie", "artist": "urn:entity:artist"}


class QlooError(RuntimeError):
    """Safe upstream error; message contains no credentials or raw body."""


@dataclass(frozen=True)
class Entity:
    id: str
    name: str
    kind: str
    author: str | None = None


class TasteTransport(Protocol):
    async def search(self, query: str, kind: str, take: int = 8) -> list[Entity]: ...
    async def books(self, seed_ids: list[str], take: int = 20, candidates: list[str] | None = None) -> list[Entity]: ...


class QlooClient:
    def __init__(self, api_key: str, *, timeout: float = 8.0, max_bytes: int = 1_000_000, transport=None,
                 call_budget: int = 400, cache_ttl: float = 600, clock=monotonic):
        if not api_key:
            raise QlooError("Live Qloo access is pending: QLOO_API_KEY is not configured.")
        self._key, self._timeout, self._max_bytes, self._transport = api_key, timeout, max_bytes, transport
        self._budget, self._ttl, self._clock = call_budget, cache_ttl, clock
        self._calls: deque[float] = deque()
        self._cache: OrderedDict[tuple, tuple[float, Any]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        try:
            async with asyncio.timeout(20):
                return await self._cached_get(path, params)
        except TimeoutError:
            raise QlooError("Qloo request timed out; try again later.") from None

    async def _cached_get(self, path: str, params: dict[str, Any]) -> Any:
        cache_key = (path, tuple(sorted(params.items())))
        # One lock coalesces identical concurrent misses and makes budget reservations atomic.
        async with self._lock:
            now = self._clock()
            cached = self._cache.get(cache_key)
            if cached and now - cached[0] < self._ttl:
                self._cache.move_to_end(cache_key)
                return cached[1]
            while self._calls and self._calls[0] <= now - 86400:
                self._calls.popleft()
            if len(self._calls) >= self._budget:
                raise QlooError("Live request budget reached; please return later.")
            self._calls.append(now)
            data = await self._request(path, params)
            self._cache[cache_key] = (self._clock(), data)
            self._cache.move_to_end(cache_key)
            while len(self._cache) > 256:
                self._cache.popitem(last=False)
            return data

    async def _request(self, path: str, params: dict[str, Any]) -> Any:
        try:
            async with asyncio.timeout(self._timeout):
                return await self._read_response(path, params)
        except TimeoutError:
            raise QlooError("Qloo request timed out; try again later.") from None

    async def _read_response(self, path: str, params: dict[str, Any]) -> Any:
        try:
            async with httpx.AsyncClient(base_url=BASE_URL, follow_redirects=False, timeout=self._timeout, transport=self._transport) as client:
                async with client.stream("GET", path, params=params, headers={"X-Api-Key": self._key, "Accept": "application/json"}) as response:
                    if 300 <= response.status_code < 400:
                        raise QlooError("Qloo redirect refused.")
                    if response.status_code in (401, 403):
                        raise QlooError("Qloo authentication failed.")
                    if response.status_code == 429:
                        raise QlooError("Qloo rate limit reached; try again later.")
                    if response.status_code >= 400:
                        raise QlooError("Qloo request failed.")
                    chunks, total = [], 0
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > self._max_bytes:
                            raise QlooError("Qloo response exceeded the safety limit.")
                        chunks.append(chunk)
                    import json
                    try: return json.loads(b"".join(chunks))
                    except (ValueError, UnicodeError): raise QlooError("Qloo returned invalid JSON.")
        except QlooError: raise
        except httpx.HTTPError:
            raise QlooError("Qloo is temporarily unavailable.") from None

    @staticmethod
    def _entity(raw: Any, expected: str) -> Entity:
        if not isinstance(raw, dict): raise QlooError("Qloo returned an unknown entity shape.")
        eid, name = raw.get("id") or raw.get("entity_id"), raw.get("name") or raw.get("title")
        if not isinstance(eid, str) or not isinstance(name, str) or not name.strip():
            raise QlooError("Qloo returned an entity without a valid ID or name.")
        try: eid = str(UUID(eid))
        except (ValueError, TypeError): raise QlooError("Qloo returned an entity without a valid UUID.")
        expected_urn = TYPE_URNS[expected]
        singular = [raw[key] for key in ("type", "entity_type") if key in raw]
        if any(not isinstance(value, str) or not value for value in singular):
            raise QlooError("Qloo returned an unexpected entity type.")
        if "types" in raw:
            types = raw["types"]
            if (not isinstance(types, list) or not types or
                    any(not isinstance(value, str) or not value for value in types) or
                    any(value != expected_urn for value in types)):
                raise QlooError("Qloo returned an unexpected entity type.")
        else:
            types = None
        if "subtype" in raw and (not isinstance(raw["subtype"], str) or raw["subtype"] != expected_urn):
            raise QlooError("Qloo returned an unexpected entity type.")
        if singular:
            if all(value == "urn:entity" for value in singular):
                if raw.get("subtype") != expected_urn:
                    raise QlooError("Qloo returned an unexpected entity type.")
            elif any(value != expected_urn for value in singular):
                raise QlooError("Qloo returned an unexpected entity type.")
        elif types is None:
            raise QlooError("Qloo returned an unexpected entity type.")
        props = raw.get("properties") if isinstance(raw.get("properties"), dict) else {}
        author = props.get("author") if isinstance(props.get("author"), str) else None
        if len(name) > 300 or (author is not None and len(author) > 300):
            raise QlooError("Qloo returned oversized entity text.")
        return Entity(eid, name.strip(), expected, author)

    async def search(self, query: str, kind: str, take: int = 8) -> list[Entity]:
        data = await self._get("/search", {"query": query, "types": TYPE_URNS[kind], "take": min(take, 10)})
        rows = data.get("results") if isinstance(data, dict) else None
        if not isinstance(rows, list): raise QlooError("Qloo returned an unknown search shape.")
        if len(rows) > min(take, 10): raise QlooError("Qloo returned too many search results.")
        return [self._entity(x, kind) for x in rows]

    async def books(self, seed_ids: list[str], take: int = 20, candidates: list[str] | None = None) -> list[Entity]:
        params = {"filter.type": TYPE_URNS["book"], "signal.interests.entities": ",".join(seed_ids), "take": min(take, 40)}
        if candidates is not None: params["filter.results.entities"] = ",".join(candidates)
        data = await self._get("/v2/insights", params)
        results = data.get("results") if isinstance(data, dict) else None
        rows = results.get("entities") if isinstance(results, dict) else None
        if not isinstance(rows, list): raise QlooError("Qloo returned an unknown insights shape.")
        if len(rows) > min(take, 40): raise QlooError("Qloo returned too many book results.")
        entities = [self._entity(x, "book") for x in rows]
        if candidates is not None and any(x.id not in candidates for x in entities):
            raise QlooError("Qloo did not honor the candidate-pool filter.")
        return entities
