"""Composition root shared by HTTP, stdio, and in-process tests."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from simovi_mcp.auth import HashedBearerVerifier
from simovi_mcp.config import Settings
from simovi_mcp.providers.swiss_transport import SwissTransport
from simovi_mcp.resources import register_resources
from simovi_mcp.tools.transit import register_transit_tools


def create_server(
    settings: Settings | None = None, *, transport: httpx.AsyncBaseTransport | None = None
) -> FastMCP:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        async with httpx.AsyncClient(
            timeout=config.upstream_timeout_seconds,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            follow_redirects=False,
            headers={"User-Agent": "simovi-mcp/0.1.0"},
            transport=transport,
        ) as client:
            yield {"swiss_transport": SwissTransport(client)}

    mcp = FastMCP(
        name="SIMOVI",
        version="0.1.0",
        instructions=(
            "Read simovi://capabilities for coverage. Only a Swiss stop-search demo "
            "is currently implemented. Never invent Infobús, GTFS, or socio-technical "
            "results. Cite sources and distinguish retrieval time from data freshness."
        ),
        auth=HashedBearerVerifier(config.token_sha256) if config.token_sha256 else None,
        lifespan=lifespan,
        mask_error_details=True,
    )
    register_transit_tools(mcp)
    register_resources(mcp)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
        """Liveness only: deliberately independent of external API availability."""
        return JSONResponse({"status": "ok", "service": "simovi-mcp"})

    return mcp
