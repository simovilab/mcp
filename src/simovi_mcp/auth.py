"""Minimal pre-shared bearer authentication for header-capable MCP clients."""

import hashlib
import hmac

from fastmcp.server.auth import AccessToken, TokenVerifier


class HashedBearerVerifier(TokenVerifier):
    def __init__(self, digest: str) -> None:
        super().__init__()
        self._digest = digest

    async def verify_token(self, token: str) -> AccessToken | None:
        actual = hashlib.sha256(token.encode()).hexdigest()
        if not hmac.compare_digest(actual, self._digest):
            return None
        return AccessToken(token=token, client_id="simovi-shared-client", scopes=["read"])
