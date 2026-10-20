import hashlib

import pytest

from simovi_mcp.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture
def protected_settings() -> Settings:
    # Public test credential, not a deployment secret.
    return Settings(
        _env_file=None,
        environment="production",
        token_sha256=hashlib.sha256(b"test-only-token").hexdigest(),
    )


@pytest.fixture
def station_payload() -> dict:
    return {
        "stations": [
            {
                "id": "8507000",
                "name": "Bern",
                "coordinate": {"type": "WGS84", "x": 46.9488, "y": 7.4391},
            },
            {
                "id": "8507001",
                "name": "Bern, Bahnhof",
                "coordinate": {"type": "WGS84", "x": None, "y": None},
            },
        ]
    }
