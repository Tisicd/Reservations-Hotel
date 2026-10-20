import os
from dataclasses import dataclass

from app.application.advance import SagaConfig


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
    availability_url: str
    payment_url: str
    customer_url: str
    hotel_url: str
    notification_url: str
    notification_read_timeout_seconds: float
    connect_timeout_seconds: float
    read_timeout_seconds: float
    payment_read_timeout_seconds: float
    saga_sync_wait_seconds: float
    hold_ttl_seconds: int
    saga_hold_deadline_seconds: int
    payment_max_technical_retries: int
    payment_reconcile_deadline_seconds: int
    confirm_deadline_seconds: int
    cancel_deadline_seconds: int
    manual_review_hold_ttl_seconds: int
    backoff_base_seconds: float
    backoff_max_seconds: float
    lease_seconds: int
    max_nights: int
    recovery_interval_seconds: float
    recovery_batch: int
    relay_interval_seconds: float
    relay_batch: int
    relay_lease_seconds: int
    log_level: str

    @property
    def db_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def saga(self) -> SagaConfig:
        return SagaConfig(
            saga_sync_wait_seconds=self.saga_sync_wait_seconds,
            hold_ttl_seconds=self.hold_ttl_seconds,
            saga_hold_deadline_seconds=self.saga_hold_deadline_seconds,
            payment_max_technical_retries=self.payment_max_technical_retries,
            payment_reconcile_deadline_seconds=self.payment_reconcile_deadline_seconds,
            confirm_deadline_seconds=self.confirm_deadline_seconds,
            cancel_deadline_seconds=self.cancel_deadline_seconds,
            manual_review_hold_ttl_seconds=self.manual_review_hold_ttl_seconds,
            backoff_base_seconds=self.backoff_base_seconds,
            backoff_max_seconds=self.backoff_max_seconds,
            lease_seconds=self.lease_seconds,
            max_nights=self.max_nights,
        )


def load_settings() -> Settings:
    password = os.environ.get("DB_PASSWORD", "")
    password_file = os.environ.get("DB_PASSWORD_FILE", "")
    if password_file:
        password = _read_secret(password_file)
    return Settings(
        db_host=os.environ.get("DB_HOST", "127.0.0.1"),
        db_port=int(os.environ.get("DB_PORT", "5433")),
        db_name=os.environ.get("DB_NAME", "reservation_db"),
        db_user=os.environ.get("DB_USER", "reservation"),
        db_password=password,
        db_pool_size=int(os.environ.get("DB_POOL_SIZE", "5")),
        db_pool_timeout=int(os.environ.get("DB_POOL_TIMEOUT", "2")),
        availability_url=os.environ.get("AVAILABILITY_URL", "http://127.0.0.1:8101"),
        payment_url=os.environ.get("PAYMENT_URL", "http://127.0.0.1:8102"),
        customer_url=os.environ.get("CUSTOMER_URL", "http://127.0.0.1:8080"),
        hotel_url=os.environ.get("HOTEL_URL", "http://127.0.0.1:8080"),
        notification_url=os.environ.get("NOTIFICATION_URL", "http://127.0.0.1:8080"),
        connect_timeout_seconds=float(os.environ.get("HTTP_CONNECT_TIMEOUT_SECONDS", "1")),
        read_timeout_seconds=float(os.environ.get("HTTP_READ_TIMEOUT_SECONDS", "2")),
        payment_read_timeout_seconds=float(
            os.environ.get("PAYMENT_READ_TIMEOUT_SECONDS", "5")
        ),
        notification_read_timeout_seconds=float(
            os.environ.get("NOTIFICATION_READ_TIMEOUT_SECONDS", "3")
        ),
        saga_sync_wait_seconds=float(os.environ.get("SAGA_SYNC_WAIT_SECONDS", "5")),
        hold_ttl_seconds=int(os.environ.get("HOLD_TTL_SECONDS", "600")),
        saga_hold_deadline_seconds=int(os.environ.get("SAGA_HOLD_DEADLINE_SECONDS", "60")),
        payment_max_technical_retries=int(
            os.environ.get("PAYMENT_MAX_TECHNICAL_RETRIES", "3")
        ),
        payment_reconcile_deadline_seconds=int(
            os.environ.get("PAYMENT_RECONCILE_DEADLINE_SECONDS", "900")
        ),
        confirm_deadline_seconds=int(os.environ.get("CONFIRM_DEADLINE_SECONDS", "120")),
        cancel_deadline_seconds=int(os.environ.get("CANCEL_DEADLINE_SECONDS", "120")),
        manual_review_hold_ttl_seconds=int(
            os.environ.get("MANUAL_REVIEW_HOLD_TTL_SECONDS", "86400")
        ),
        backoff_base_seconds=float(os.environ.get("BACKOFF_BASE_SECONDS", "0.5")),
        backoff_max_seconds=float(os.environ.get("BACKOFF_MAX_SECONDS", "30")),
        lease_seconds=int(os.environ.get("LEASE_SECONDS", "15")),
        max_nights=int(os.environ.get("MAX_NIGHTS", "30")),
        recovery_interval_seconds=float(os.environ.get("RECOVERY_INTERVAL_SECONDS", "2")),
        recovery_batch=int(os.environ.get("RECOVERY_BATCH", "20")),
        relay_interval_seconds=float(os.environ.get("RELAY_INTERVAL_SECONDS", "1")),
        relay_batch=int(os.environ.get("RELAY_BATCH", "20")),
        relay_lease_seconds=int(os.environ.get("RELAY_LEASE_SECONDS", "30")),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
