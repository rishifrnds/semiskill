import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    database_url: str
    protected_paths: tuple[str, ...]

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            database_url=os.environ.get(
                "DATABASE_URL",
                "postgresql://semiskill:semiskill@localhost:5432/semiskill",
            ),
            protected_paths=(
                "semiskill/spine/",
                "semiskill/artifacts/",
                "semiskill/governance/",
            ),
        )
