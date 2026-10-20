import os
from dataclasses import dataclass


def _read_secret(path: str) -> str:
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    return ""


def _bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes")


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_pool_size: int
    db_pool_timeout: int
    payment_simulation_enabled: bool
    provider_timeout_seconds: float
    provider_slow_seconds: float
    reconcile_interval_seconds: int
    reconcile_min_age_seconds: int
    reconcile_batch: int
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
        db_name=os.environ.get("DB_NAME", "payment_db"),
        db_user=os.environ.get("DB_USER", "payment"),
        db_password=password,
        db_pool_size=int(os.environ.get("DB_POOL_SIZE", "5")),
        db_pool_timeout=int(os.environ.get("DB_POOL_TIMEOUT", "2")),
        payment_simulation_enabled=_bool("PAYMENT_SIMULATION_ENABLED", False),
        provider_timeout_seconds=float(os.environ.get("PROVIDER_TIMEOUT_SECONDS", "3")),
        provider_slow_seconds=float(os.environ.get("PROVIDER_SLOW_SECONDS", "6")),
        reconcile_interval_seconds=int(os.environ.get("RECONCILE_INTERVAL_SECONDS", "5")),
        reconcile_min_age_seconds=int(os.environ.get("RECONCILE_MIN_AGE_SECONDS", "2")),
        reconcile_batch=int(os.environ.get("RECONCILE_BATCH", "100")),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
