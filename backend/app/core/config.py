import os
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.environ.get("SCNS_ENV_FILE", "../.env"), extra="ignore"
    )
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://scns:scns_local@localhost:54329/scns"
    demo_enabled: bool = False
    public_app_url: str = Field(default="http://localhost:5173", max_length=180)
    walking_speed_mps: float = Field(default=1.4, gt=0, le=3)
    gps_max_accuracy_m: float = Field(default=20, gt=0, le=50)
    gps_max_age_seconds: int = Field(default=60, ge=10, le=120)
    gps_max_path_distance_m: float = Field(default=25, gt=0, le=50)
    gps_max_landmark_distance_m: float = Field(default=40, gt=0, le=100)
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    storage_root: str = "../storage"
    import_byte_limit: int = Field(default=5 * 1024 * 1024, ge=1024, le=10 * 1024 * 1024)
    import_row_limit: int = Field(default=2000, ge=1, le=10000)
    import_parse_seconds: int = Field(default=30, ge=1, le=120)
    import_storage_limit: int = Field(default=100 * 1024 * 1024, ge=1024)
    graph_node_limit: int = Field(default=50000, gt=0)
    graph_edge_limit: int = Field(default=150000, gt=0)
    session_cookie_secure: bool = False  # Local HTTP only; deployment remains gated.
    session_ttl_seconds: int = Field(default=28800, ge=300, le=86400)
    login_account_limit: int = Field(default=5, ge=1, le=20)
    login_ip_limit: int = Field(default=30, ge=1, le=100)
    login_window_seconds: int = Field(default=900, ge=60, le=3600)

    @model_validator(mode="after")
    def canonical_url(self):
        from urllib.parse import urlsplit

        url = urlsplit(self.public_app_url)
        if (
            any(c.isspace() or ord(c) < 32 for c in self.public_app_url)
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path not in ("", "/")
            or not url.hostname
            or url.scheme not in ("http", "https")
            or (url.scheme == "http" and url.hostname not in ("localhost", "127.0.0.1", "::1"))
        ):
            raise ValueError(
                "PUBLIC_APP_URL needs an HTTPS origin; local HTTP loopback is demo-only"
            )
        try:
            _ = url.port
        except ValueError as error:
            raise ValueError("Invalid canonical origin port") from error
        self.public_app_url = self.public_app_url.rstrip("/")
        return self

    @model_validator(mode="after")
    def production_guard(self):
        if self.app_env == "production":
            raise ValueError(
                "Production is gated until the deployment milestone; use development or test."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
