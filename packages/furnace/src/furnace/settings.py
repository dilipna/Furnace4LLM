"""Runtime settings, read from environment (prefix FURNACE_) or a .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_MASTER_KEY = "ZGV2LW9ubHktbWFzdGVyLWtleS0zMi1ieXRlcy0hISE="
DEV_SESSION_SECRET = "dev-only-session-secret"  # noqa: S105 - dev placeholder, rejected when env=prod


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FURNACE_", env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = "postgresql+asyncpg://furnace:furnace@localhost:5433/furnace"
    # Master key for BYOK secrets at rest (base64, 32 bytes) and the session signing secret.
    # Dev defaults are deliberately obvious; with env=prod the settings refuse to load them.
    master_key: SecretStr = SecretStr(DEV_MASTER_KEY)
    session_secret: SecretStr = SecretStr(DEV_SESSION_SECRET)
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
    # Live views: stream the lab endpoint's /metrics (+ NVML on this host) and allow small
    # on-demand benchmark runs against it. Off on hosted deployments without a lab endpoint.
    live_lab: bool = True
    # What webhook-triggered Guard runs use on the runner (see docs/github-app.md).
    guard_suite_path: Path | None = None
    guard_questions_path: Path | None = None
    guard_max_prompt_tokens: int | None = None

    @model_validator(mode="after")
    def _no_dev_secrets_in_prod(self) -> Settings:
        if self.env == "prod":
            if self.master_key.get_secret_value() == DEV_MASTER_KEY:
                raise ValueError("FURNACE_MASTER_KEY must be set in production")
            if self.session_secret.get_secret_value() == DEV_SESSION_SECRET:
                raise ValueError("FURNACE_SESSION_SECRET must be set in production")
            if self.labels_writable:
                raise ValueError("set FURNACE_LABELS_WRITABLE=false in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
