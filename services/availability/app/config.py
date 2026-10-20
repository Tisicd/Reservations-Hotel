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
    hold_default_ttl_seconds: int
    hold_max_ttl_seconds: int
    max_nights: int
    max_units: int
    expiry_interval_seconds: int
    expiry_batch: int
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
        db_name=os.environ.get("DB_NAME", "availability_db"),
        db_user=os.environ.get("DB_USER", "availability"),
        db_password=password,
        db_pool_size=int(os.environ.get("DB_POOL_SIZE", "5")),
        db_pool_timeout=int(os.environ.get("DB_POOL_TIMEOUT", "2")),
        hold_default_ttl_seconds=int(os.environ.get("HOLD_DEFAULT_TTL_SECONDS", "600")),
        hold_max_ttl_seconds=int(os.environ.get("HOLD_MAX_TTL_SECONDS", "3600")),
        max_nights=int(os.environ.get("MAX_NIGHTS", "30")),
        max_units=int(os.environ.get("MAX_UNITS", "10")),
        expiry_interval_seconds=int(os.environ.get("EXPIRY_INTERVAL_SECONDS", "5")),
        expiry_batch=int(os.environ.get("EXPIRY_BATCH", "100")),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
