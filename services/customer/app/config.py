import dataclasses
import os
import pathlib


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _int(name: str, default: int) -> int:
    return int(_env(name, str(default)))


def _password() -> str:
    path = os.getenv("DB_PASSWORD_FILE", "")
    if path and os.path.exists(path):
        return pathlib.Path(path).read_text(encoding="utf-8").strip()
    return os.getenv("DB_PASSWORD", "")


@dataclasses.dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_pool_size: int
    db_pool_timeout: int
    log_level: str
    scrypt_n: int
    scrypt_r: int
    scrypt_p: int
    auth_session_ttl_seconds: int
    login_max_failures: int
    login_lock_seconds: int

    @property
    def db_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


def load_settings() -> Settings:
    return Settings(
        db_host=_env("DB_HOST", "127.0.0.1"),
        db_port=_int("DB_PORT", 5433),
        db_name=_env("DB_NAME", "customer_db"),
        db_user=_env("DB_USER", "customer"),
        db_password=_password(),
        db_pool_size=_int("DB_POOL_SIZE", 5),
        db_pool_timeout=_int("DB_POOL_TIMEOUT", 5),
        log_level=_env("LOG_LEVEL", "INFO"),
        scrypt_n=_int("SCRYPT_N", 32768),
        scrypt_r=_int("SCRYPT_R", 8),
        scrypt_p=_int("SCRYPT_P", 1),
        auth_session_ttl_seconds=_int("AUTH_SESSION_TTL_SECONDS", 8 * 3600),
        login_max_failures=_int("LOGIN_MAX_FAILURES", 5),
        login_lock_seconds=_int("LOGIN_LOCK_SECONDS", 300),
    )
