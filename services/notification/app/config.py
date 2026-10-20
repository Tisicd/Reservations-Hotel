import os
from dataclasses import dataclass


def _read_secret(path: str) -> str:
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    return ""


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_pool_size: int
    db_pool_timeout: int
    max_attempts: int
    backoff_base_seconds: float
    backoff_max_seconds: float
    lease_seconds: int
    worker_interval_seconds: float
    worker_batch: int
    log_level: str

    @property
    def db_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


def load_settings() -> Settings:
    password = os.environ.get("DB_PASSWORD", "")
    password_file = os.environ.get("DB_PASSWORD_FILE", "")
    if password_file:
        password = _read_secret(password_file)
    return Settings(
        db_host=os.environ.get("DB_HOST", "127.0.0.1"),
        db_port=int(os.environ.get("DB_PORT", "5433")),
        db_name=os.environ.get("DB_NAME", "notification_db"),
        db_user=os.environ.get("DB_USER", "notification"),
        db_password=password,
        db_pool_size=int(os.environ.get("DB_POOL_SIZE", "5")),
        db_pool_timeout=int(os.environ.get("DB_POOL_TIMEOUT", "2")),
        max_attempts=int(os.environ.get("NOTIFICATION_MAX_ATTEMPTS", "5")),
        backoff_base_seconds=float(os.environ.get("NOTIFICATION_BACKOFF_BASE_SECONDS", "1")),
        backoff_max_seconds=float(os.environ.get("NOTIFICATION_BACKOFF_MAX_SECONDS", "30")),
        lease_seconds=int(os.environ.get("NOTIFICATION_LEASE_SECONDS", "30")),
        worker_interval_seconds=float(
            os.environ.get("NOTIFICATION_WORKER_INTERVAL_SECONDS", "1")
        ),
        worker_batch=int(os.environ.get("NOTIFICATION_WORKER_BATCH", "20")),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
