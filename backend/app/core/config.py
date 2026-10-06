from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://scns:scns_local@localhost:54329/scns"
    demo_enabled: bool = False
    walking_speed_mps: float = Field(default=1.4, gt=0, le=3)
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    storage_root: str = "../storage"
    graph_node_limit: int = Field(default=50000, gt=0)
    graph_edge_limit: int = Field(default=150000, gt=0)

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
