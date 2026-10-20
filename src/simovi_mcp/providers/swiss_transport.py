"""Read-only adapter for https://transport.opendata.ch/docs.html."""

import asyncio
from datetime import UTC, datetime
from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from simovi_mcp.domain.transit import Stop, StopSearchResult

BASE_URL = "https://transport.opendata.ch/v1/"


class ProviderError(Exception):
    """A safe, actionable provider error that can be shown to MCP clients."""


class Coordinate(BaseModel):
    type: Literal["WGS84"]
    x: float | None = Field(default=None, ge=-90, le=90)
    y: float | None = Field(default=None, ge=-180, le=180)


class Station(BaseModel):
    id: str | None
    name: str
    coordinate: Coordinate


class Locations(BaseModel):
    stations: list[Station]


class SwissTransport:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self._slots = asyncio.Semaphore(5)

    async def search_stops(self, query: str, limit: int) -> StopSearchResult:
        try:
            async with self._slots:
                response = await self._client.get(
                    f"{BASE_URL}locations", params={"query": query, "type": "station"}
                )
            if response.status_code == 429:
                raise ProviderError("Demo transport provider is rate limited; try again later.")
            response.raise_for_status()
            payload = Locations.model_validate(response.json())
        except httpx.TimeoutException as exc:
            raise ProviderError("Demo transport provider timed out; try again later.") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("Demo transport provider is unavailable; try again later.") from exc
        except (ValueError, ValidationError) as exc:
            raise ProviderError("Demo transport provider returned an unexpected response.") from exc

        stations = [station for station in payload.stations if station.id is not None]
        return StopSearchResult(
            source_url=str(response.url),
            retrieved_at=datetime.now(UTC),
            query=query,
            stops=[
                Stop(
                    source_id=station.id,
                    name=station.name,
                    latitude=station.coordinate.x,
                    longitude=station.coordinate.y,
                )
                for station in stations[:limit]
                if station.id is not None
            ],
            truncated=len(stations) > limit,
        )
