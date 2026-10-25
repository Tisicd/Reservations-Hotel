import datetime as dt
import re
import secrets
import uuid

from .config import Settings
from .errors import InvalidCredentials, ValidationError
from .models import CustomerStore
from .security import (
    fake_hash,
    hash_password,
    hash_token,
    validate_password,
    verify_password,
)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _aware(value):
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=dt.UTC)
    return value


class AuthService:
    def __init__(self, store: CustomerStore, settings: Settings):
        self.store = store
        self.settings = settings

    def _normalize(self, name: str, email: str) -> tuple[str, str]:
        name = (name or "").strip()
        email = (email or "").strip().lower()
        if not 1 <= len(name) <= 120:
            raise ValidationError("name debe tener entre 1 y 120 caracteres")
        if len(email) > 254 or not EMAIL_RE.match(email):
            raise ValidationError("email inválido")
        return name, email

    def register(self, name: str, email: str, password: str) -> dict:
        name, email = self._normalize(name, email)
        validate_password(password, name, email)
        password_hash = hash_password(
            password, self.settings.scrypt_n,
            self.settings.scrypt_r, self.settings.scrypt_p)
        return self.store.register(
            uuid.uuid4(), name, email, password_hash)

    def login(self, email: str, password: str) -> dict:
        email = (email or "").strip().lower()
        row = self.store.get_by_email(email)
        encoded = (row or {}).get("password_hash")
        if row is None or not encoded:
            encoded = fake_hash(
                self.settings.scrypt_n,
                self.settings.scrypt_r,
                self.settings.scrypt_p,
            )
        ok = verify_password(password or "", encoded)
        now = _now()
        locked = bool(row and _aware(row.get("locked_until"))
                      and _aware(row["locked_until"]) > now)
        if row is None or not ok or locked:
            if row is not None and not locked:
                self.store.record_failure(
                    row["id"], self.settings.login_max_failures,
                    self.settings.login_lock_seconds)
            raise InvalidCredentials("credenciales inválidas")

        self.store.record_success(row["id"])
        self.store.delete_expired_sessions()
        token = secrets.token_urlsafe(32)
        expires_at = now + dt.timedelta(
            seconds=self.settings.auth_session_ttl_seconds)
        self.store.create_session(hash_token(token), row["id"], expires_at)
        customer = {
            "id": str(row["id"]),
            "name": row["name"],
            "email": row["email"],
        }
        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": self.settings.auth_session_ttl_seconds,
            "customer": customer,
        }

    def logout(self, token: str) -> None:
        self.store.delete_session(hash_token(token))

    def validate(self, token: str) -> dict | None:
        if not token:
            return None
        return self.store.get_session(hash_token(token))

    def me(self, token: str) -> dict:
        customer = self.validate(token)
        if customer is None:
            raise InvalidCredentials("credenciales inválidas")
        return {
            "id": str(customer["id"]),
            "name": customer["name"],
            "email": customer["email"],
        }
