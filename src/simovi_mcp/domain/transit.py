"""Small transit contracts, without claiming provider IDs are GTFS IDs."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Stop(BaseModel):
    source_id: str
    name: str
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class StopSearchResult(BaseModel):
    source: Literal["transport.opendata.ch"] = "transport.opendata.ch"
    source_url: str
    retrieved_at: datetime
    coverage: Literal["Switzerland (demo; not Infobús)"] = "Switzerland (demo; not Infobús)"
    data_kind: Literal["stop_directory"] = "stop_directory"
    query: str
    stops: list[Stop]
    truncated: bool
