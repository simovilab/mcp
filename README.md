# SIMOVI MCP

FastMCP server for conversational access to public transportation data and, later,
the socio-technical system around it.

**Implemented:** a read-only Swiss stop-search demo and a capabilities resource.
**Not yet implemented:** Infobús, GTFS queries, fares, real-time service, or SPARQL.
The demo is not evidence of SIMOVI's geographic or service coverage.

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Python 3.13 (uv can install it).

```sh
uv sync --frozen
uv run simovi-mcp
```

Streamable HTTP: `http://127.0.0.1:8000/mcp`.
Liveness: `http://127.0.0.1:8000/health`.
Local stdio: `uv run simovi-mcp --transport stdio`.
No credentials are needed for the Swiss demo API. Local HTTP defaults to
unauthenticated loopback; binding a non-loopback address requires authentication.
The stdio transport relies on local process permissions, not bearer auth.

If Python reports `ModuleNotFoundError: simovi_mcp` despite a successful sync on
macOS, check whether the generated editable-install `.pth` file is marked hidden:
Python 3.13 skips such files. `uv run --no-editable simovi-mcp` avoids `.pth` files
by installing the application normally. Use the same `--no-editable` option for
other `uv run` checks in that environment; resync/restart after editing source.

### Try a tool

Start the HTTP server above, then run this Python example in the project environment
(for example using `uv run python`):

```python
import asyncio
from fastmcp import Client


async def main():
    async with Client("http://127.0.0.1:8000/mcp") as client:
        print(await client.list_tools())
        print(await client.read_resource("simovi://capabilities"))
        result = await client.call_tool("demo_search_swiss_stops", {"query": "Bern", "limit": 3})
        print(result.structured_content)


asyncio.run(main())
```

Example conversational request: “Find stations named Bern in the Swiss demo.”
Results include provider IDs, WGS84 coordinates, source URL, UTC retrieval time,
and whether the **returned provider matches** were truncated. The upstream may
return only its best matches; this is not an exhaustive station inventory.
Retrieval time does not mean the underlying dataset was updated at that time.

## Structure

- `src/simovi_mcp/server.py`: composition, shared HTTP-client lifespan, liveness.
- `src/simovi_mcp/config.py`, `auth.py`: validated settings and bearer verification.
- `src/simovi_mcp/domain/`: typed domain contracts, independent of MCP.
- `src/simovi_mcp/providers/`: external service adapters; start with Swiss Transport.
- `src/simovi_mcp/tools/`: MCP tools grouped by domain; thin adapters over providers.
- `src/simovi_mcp/resources.py`: implemented coverage and explicitly unavailable roadmap.
- `tests/`: offline provider, MCP, HTTP authentication, and configuration tests.
- `Dockerfile`, `compose.yaml`: immutable application image and existing-Traefik routing.

No database, ontology, arbitrary URL fetcher, or generic query executor is needed
for this starting point.

## Deploy behind an existing Traefik instance

The endpoint will be **`https://mcp.simovi.org/mcp`**, not the domain root.
This repository does not provision DNS, install Traefik, or deploy itself.

Prerequisites:

1. Point the domain's DNS A/AAAA records at your server (only publish working IPv6).
2. Traefik must have its Docker provider enabled, access to application labels,
   a TLS entrypoint, and a configured ACME certificate resolver. Its ACME challenge
   requirements must be reachable (for example ports 80/443 for HTTP/TLS challenges).
3. Traefik and this application must share an **existing external Docker network**.
4. Set the network, entrypoint, and resolver names to those in your installation;
   the defaults `traefik`, `websecure`, and `letsencrypt` are examples.

```sh
cp .env.example .env
```

Create a random token with at least 32 bytes of entropy using your password manager,
and save the original there for MCP clients. The server stores only a SHA-256 digest.
Use this hidden-input command to append that digest to your local `.env`:

```sh
uv run python -c 'import getpass, hashlib, os; from pathlib import Path; token = getpass.getpass("Bearer token from password manager: "); assert len(token) >= 43, "Use a randomly generated token with at least 32 bytes of entropy"; p = Path(".env"); f = p.open("a"); f.write("\nSIMOVI_TOKEN_SHA256=" + hashlib.sha256(token.encode()).hexdigest() + "\n"); f.close(); os.chmod(p, 0o600)'
```

Length validation cannot guarantee entropy: do not use a memorable password.
Edit `.env` to match your Traefik installation, then on the deployment host:

```sh
docker compose config --quiet
docker compose up -d --build
curl --fail https://mcp.simovi.org/health
```

Do not print or share expanded Compose configuration containing credentials.
The application publishes **no host port**; Traefik terminates TLS and forwards to
container port 8000. Source code is built into the image, not bind-mounted. The
image runs non-root with a read-only filesystem; dependencies are locked in `uv.lock`.
The container's health check is liveness, not a guarantee the public API is healthy.

The router preserves `/mcp` and explicitly flushes streamed responses. Avoid proxy
buffering/compression middleware for MCP streams, and review your existing Traefik
entrypoint timeouts if you later add long-running tools. HTTP is stateless, so MCP
session affinity is not required. No HTTP-to-HTTPS router is installed here; configure
your existing Traefik entrypoint redirect if desired.

### Client connection and authentication

Configure a remote MCP client with URL `https://mcp.simovi.org/mcp` and an
`Authorization: Bearer <token>` header, entering the original token through the
client's secure credential facility. For a Python client, load a token into an
environment variable through your secret manager before running:

```python
import os
from fastmcp import Client

client = Client(
    "https://mcp.simovi.org/mcp",
    auth=os.environ["SIMOVI_MCP_TOKEN"],
)
```

This initial authentication scheme is a **shared bearer credential**, with no user
identity, OAuth discovery, token issuance, expiration, or per-user scopes. Rotate it
by replacing the configured digest and recreating the container; revoke access by
rotating the credential. `/health` is deliberately public and discloses no secrets.

Some conversational clients require OAuth rather than accepting custom headers.
For those, replace the verifier with a FastMCP OAuth/remote-identity provider before
connecting; the scaffold does not promise compatibility with every hosted client.
TLS alone is not authentication. Add edge rate limits and monitoring before broad
public use; the demo provider's semaphore is per process, not a global rate limiter.
Host/Origin validation is enabled. CORS is intentionally not enabled: most hosted
conversational clients connect server-to-server. Direct browser clients need both an
explicit trusted-origin allowlist and appropriately scoped CORS middleware.

## Add real services

### Infobús and GTFS

Add `providers/infobus.py` after confirming the API contract, authentication, coverage,
licensing, and request limits. Put upstream credentials in server-side settings,
never MCP arguments or responses. Map responses into domain models, then register
focused tools through `server.py`:

- `search_stops`, `get_stop`, `list_routes`, `get_route`.
- `get_trip`, `get_stop_departures`, `get_service_calendar`.
- `get_fares`, distinguishing fare rules and rider categories.

These names are recommendations, **not currently available tools**. Namespace IDs
by provider/feed and retain original GTFS identifiers. Add explicit feed version,
service date, agency timezone, language, provenance, and scheduled-vs-realtime fields.
GTFS times can exceed `24:00:00`; do not parse them as ordinary wall-clock times.
Do not claim a service is absent when its feed, calendar, or realtime coverage is
unknown. Add bounded pagination, per-provider caching, and quota-aware retries before
larger traffic; do not retry authentication or invalid-query errors.

The demo adapter uses fixed HTTPS endpoints, pooled async HTTP, a timeout, a
five-request concurrency cap, schema validation, and sanitized errors. It does not
yet cache or automatically retry; respect the public provider's shared capacity.

### Socio-technical knowledge and SPARQL

Add separate `domain/knowledge.py`, `providers/sparql.py`, and `tools/knowledge.py`
when a real endpoint and vocabulary are selected. Model organizations, stakeholders,
principles, technologies, and data components independently of GTFS, and link them
using stable URIs and explicit relationship semantics. Include provenance, named graph,
and validity dates where available; GTFS is not an ontology for all these concepts.

Prefer focused tools such as `describe_organization`, `find_stakeholders`, or
`trace_data_dependencies` over exposing arbitrary SPARQL. Use reviewed read-only
query templates with safely serialized RDF terms, fixed/allowlisted endpoints,
bounded results, timeouts, and blocked `SERVICE`/update operations. Treat all
upstream descriptions as untrusted data, never instructions.

Update `simovi://capabilities` only when features actually work. Add prompts once
the real domain interactions are known rather than baking in speculative workflows.

## Development checks

```sh
uv sync --frozen
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
docker build -t simovi-mcp:local .
```

Tests use mocked upstream HTTP and require neither network nor deployment secrets.
CI runs the same checks, validates Compose, and builds the image. Upgrade dependencies
deliberately with `uv lock --upgrade` and review the resulting lockfile.

## References

- [FastMCP HTTP deployment](https://gofastmcp.com/deployment/http)
- [FastMCP authentication](https://gofastmcp.com/servers/auth/authentication)
- [Swiss Transport API and usage limits](https://transport.opendata.ch/docs.html)
- [GTFS reference](https://gtfs.org/documentation/)
