import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    database_url: str
    protected_paths: tuple[str, ...]

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            # DATABASE_URL is the contract. The fallback below is a LOCAL-DEV-ONLY convenience that
            # points at the loopback docker-compose DB with its non-secret dev credentials
            # (see .env.example / docker-compose.yml). Any real deployment sets DATABASE_URL from a
            # secret; these credentials grant nothing beyond a throwaway local container.
            database_url=os.environ.get(
                "DATABASE_URL",
                # 127.0.0.1 (not "localhost"): on Windows "localhost" resolves to IPv6 ::1 first,
                # which the IPv4-bound docker DB never answers, stalling every connection ~30s.
                "postgresql://semiskill:semiskill@127.0.0.1:5432/semiskill",
            ),
            protected_paths=(
                "semiskill/spine/",
                "semiskill/artifacts/",
                "semiskill/governance/",
            ),
        )
