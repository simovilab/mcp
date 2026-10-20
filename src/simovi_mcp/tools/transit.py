"""Transit tools with bounded inputs and explicit geographic coverage."""

from typing import Annotated, cast

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field, StringConstraints

from simovi_mcp.domain.transit import StopSearchResult
from simovi_mcp.providers.swiss_transport import ProviderError, SwissTransport

SearchQuery = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]


def register_transit_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        tags={"transit", "demo"},
        annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True},
    )
    async def demo_search_swiss_stops(
        query: SearchQuery,
        ctx: Context,
        limit: Annotated[int, Field(ge=1, le=20)] = 5,
    ) -> StopSearchResult:
        """Find Swiss stops/stations by name (e.g. Bern), using a public demo API.

        Switzerland only: NOT Infobús or local SIMOVI coverage. Returns provider-scoped
        IDs and WGS84 coordinates, not GTFS IDs, departures, fares, or real-time data.
        Empty results mean no matches in this provider, not proof a stop does not exist.
        """
        provider = cast(SwissTransport, ctx.lifespan_context["swiss_transport"])
        try:
            return await provider.search_stops(query, limit)
        except ProviderError as exc:
            raise ToolError(str(exc)) from exc
