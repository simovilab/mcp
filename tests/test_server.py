import json

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from pydantic import ValidationError
from starlette.testclient import TestClient

from simovi_mcp.config import Settings
from simovi_mcp.server import create_server


async def test_mcp_tool_and_resource(settings: Settings, station_payload: dict) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=station_payload))
    async with Client(create_server(settings, transport=transport)) as client:
        tools = await client.list_tools()
        assert [tool.name for tool in tools] == ["demo_search_swiss_stops"]
        result = await client.call_tool("demo_search_swiss_stops", {"query": " Bern ", "limit": 1})
        assert result.structured_content["stops"][0]["source_id"] == "8507000"
        assert result.structured_content["query"] == "Bern"
        resources = await client.read_resource("simovi://capabilities")
        capabilities = json.loads(resources[0].text)
        assert "socio_technical" in capabilities["planned_not_available"]


@pytest.mark.parametrize(
    "arguments",
    [{"query": " "}, {"query": "a"}, {"query": "x" * 121}, {"query": "Bern", "limit": 21}],
)
async def test_bad_arguments_do_not_call_provider(settings: Settings, arguments: dict) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Invalid input reached upstream")

    async with Client(create_server(settings, transport=httpx.MockTransport(handler))) as client:
        with pytest.raises(ToolError):
            await client.call_tool("demo_search_swiss_stops", arguments)


async def test_provider_error_is_actionable(settings: Settings) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(503, text="private details"))
    async with Client(create_server(settings, transport=transport)) as client:
        with pytest.raises(ToolError, match="unavailable"):
            await client.call_tool("demo_search_swiss_stops", {"query": "Bern"})


def test_auth_health_and_host_guard(protected_settings: Settings) -> None:
    app = create_server(protected_settings).http_app(
        path="/mcp",
        stateless_http=True,
        json_response=True,
        host_origin_protection=True,
        allowed_hosts=protected_settings.allowed_hosts,
        allowed_origins=protected_settings.allowed_origins,
    )
    with TestClient(app, base_url="https://mcp.simovi.org") as client:
        assert client.get("/health").json()["status"] == "ok"
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {
                "_meta": {
                    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                    "io.modelcontextprotocol/clientCapabilities": {},
                }
            },
        }
        headers = {
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2026-07-28",
            "MCP-Method": "tools/list",
        }
        assert client.post("/mcp", json=payload, headers=headers).status_code == 401
        headers["Authorization"] = "Bearer incorrect"
        assert client.post("/mcp", json=payload, headers=headers).status_code == 401
        headers["Authorization"] = "Bearer test-only-token"
        response = client.post("/mcp", json=payload, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["result"]["tools"][0]["name"] == "demo_search_swiss_stops"
        headers["Origin"] = "https://untrusted.example"
        assert client.post("/mcp", json=payload, headers=headers).status_code in {400, 403}
        del headers["Origin"]
        headers["Host"] = "untrusted.example"
        assert client.post("/mcp", json=payload, headers=headers).status_code in {400, 421}


@pytest.mark.parametrize(
    "overrides", [{"environment": "production"}, {"host": "0.0.0.0"}, {"token_sha256": "bad"}]
)
def test_unsafe_settings_rejected(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **overrides)
