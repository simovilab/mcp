import httpx
import pytest

from simovi_mcp.providers.swiss_transport import ProviderError, SwissTransport


async def test_search_normalizes_and_bounds_results(station_payload: dict) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "transport.opendata.ch"
        assert dict(request.url.params) == {"query": "Bern", "type": "station"}
        return httpx.Response(200, json=station_payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await SwissTransport(client).search_stops("Bern", 1)
    assert len(result.stops) == 1
    assert result.stops[0].source_id == "8507000"
    assert result.stops[0].latitude == 46.9488
    assert result.stops[0].longitude == 7.4391
    assert result.truncated
    assert result.retrieved_at.tzinfo is not None
    assert "Switzerland" in result.coverage


@pytest.mark.parametrize(
    ("status", "body", "message"),
    [
        (429, {}, "rate limited"),
        (503, {}, "unavailable"),
        (302, {}, "unavailable"),
        (200, {"stations": "invalid"}, "unexpected response"),
        (200, {"private": "not for clients"}, "unexpected response"),
    ],
)
async def test_upstream_errors_are_sanitized(status: int, body: dict, message: str) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(status, json=body))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ProviderError, match=message):
            await SwissTransport(client).search_stops("Bern", 5)


async def test_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("internal upstream details", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError, match="timed out"):
            await SwissTransport(client).search_stops("Bern", 5)


async def test_empty_result() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"stations": []}))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await SwissTransport(client).search_stops("Unknown", 5)
    assert result.stops == []
    assert not result.truncated
