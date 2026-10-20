"""Application settings; upstream credentials belong here, never in tool arguments."""

from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SIMOVI_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    environment: Literal["development", "production"] = "development"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    token_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$", repr=False)
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "mcp.simovi.org"]
    allowed_origins: list[str] = ["https://mcp.simovi.org"]
    upstream_timeout_seconds: float = Field(default=10, gt=0, le=60)

    @model_validator(mode="after")
    def require_production_auth(self) -> Self:
        if self.environment == "production" and not self.token_sha256:
            raise ValueError("Production requires SIMOVI_TOKEN_SHA256.")
        if self.host not in {"127.0.0.1", "::1", "localhost"} and not self.token_sha256:
            raise ValueError("Non-loopback binding requires SIMOVI_TOKEN_SHA256.")
        return self
