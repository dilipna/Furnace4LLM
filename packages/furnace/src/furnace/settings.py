"""Runtime settings, read from environment (prefix FURNACE_) or a .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FURNACE_", env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = "postgresql+asyncpg://furnace:furnace@localhost:5433/furnace"
    # AES-GCM master key for BYOK secrets at rest (base64, 32 bytes). Dev default is
    # deliberately obvious; production refuses to start with it (see security.crypto).
    master_key: SecretStr = SecretStr("ZGV2LW9ubHktbWFzdGVyLWtleS0zMi1ieXRlcy0hISE=")
    session_secret: SecretStr = SecretStr("dev-only-session-secret")
    blob_backend: str = "local"  # local | s3
    blob_dir: Path = Path(".data/blobs")
    s3_endpoint: str | None = None
    s3_bucket: str | None = None
    s3_access_key: SecretStr | None = None
    s3_secret_key: SecretStr | None = None
    web_origin: str = "http://localhost:3000"
    worker_id: str = Field(default="worker-local")
    job_lease_seconds: int = 120
    embedded_worker: bool = False  # run the cpu queue inside the API process
    # FurnaceBench results and labels served read-only by the API (default: <repo>/bench).
    bench_dir: Path | None = None
    # The labeling endpoint appends human labels to bench/labels; off in hosted deployments.
    labels_writable: bool = True
    # GitHub App (see docs/github-app.md). The private key is read from a file, never from env text.
    github_app_id: str | None = None
    github_private_key_path: Path | None = None
    github_webhook_secret: SecretStr | None = None
    # Inference endpoint the runner benchmarks and evaluates against (OpenAI-compatible).
    lab_base_url: str = "http://localhost:8100/v1"
    lab_model: str = "lab"


@lru_cache
def get_settings() -> Settings:
    return Settings()
