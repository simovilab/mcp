"""HTTP by default; stdio remains available for local subprocess clients."""

import argparse

from simovi_mcp.config import Settings
from simovi_mcp.server import create_server


def main() -> None:
    parser = argparse.ArgumentParser(description="SIMOVI MCP server")
    parser.add_argument("--transport", choices=["http", "stdio"], default="http")
    args = parser.parse_args()
    settings = Settings()
    server = create_server(settings)
    if args.transport == "stdio":
        server.run(transport="stdio", show_banner=False)
    else:
        server.run(
            transport="http",
            host=settings.host,
            port=settings.port,
            path="/mcp",
            stateless_http=True,
            host_origin_protection=True,
            allowed_hosts=settings.allowed_hosts,
            allowed_origins=settings.allowed_origins,
            show_banner=False,
        )


if __name__ == "__main__":
    main()
