"""Hashing de contraseñas, política y tokens de sesión (solo stdlib)."""

import base64
import binascii
import hashlib
import hmac
import secrets
import threading
from functools import lru_cache

from .errors import WeakPassword

# Limita el uso concurrente de scrypt para no agotar la CPU con logins.
_HASH_SEMAPHORE = threading.BoundedSemaphore(2)

COMMON_PASSWORDS = frozenset({
    "1234567890", "123456789012", "123456789a", "password", "password1",
    "password123", "contrasena", "contrasena1", "qwertyuiop", "qwerty123",
    "abc1234567", "iloveyou", "admin12345", "administrador", "bienvenido",
    "bienvenida", "welcome123", "letmein123", "monkey1234", "dragon1234",
    "football1", "baseball1", "superman1", "batman1234", "starwars1",
    "naruto1234", "pokemon123", "minecraft1", "fortnite12", "hola123456",
    "holamundo1", "reservas123", "hotel12345", "hotelreserv", "viajes1234",
    "vacaciones", "verano2026", "invierno26", "primavera26", "otono2026",
    "enero2026", "febrero2026", "marzo2026", "abril2026", "mayo2026",
    "junio2026", "julio2026", "agosto2026", "septiembre", "octubre2026",
    "noviembre", "diciembre", "cumpleanos", "familia123", "amigos1234",
    "amor123456", "teamo12345", "mipassword", "micontrasena", "usuario123",
    "invitado12", "demo123456", "prueba1234", "test123456", "temporal12",
    "cambiar123", "seguridad1", "secreto123", "privado123", "cuenta1234",
    "acceso1234", "entrar1234", "login12345", "sistema123", "servidor1",
    "internet1", "telefono1", "computador", "portatil12", "universidad",
    "estudiante", "profesor1", "uce1234567", "quito12345", "ecuador123",
    "guayaquil1", "cuenca1234", "andes12345", "pichincha1", "cotopaxi12",
    "galapagos1", "amazonia12", "sierra1234", "costa12345", "oriente123",
    "turismo123", "aventura12", "explorar1", "descubre12", "reserva2026",
    "habitacion", "habitacion1", "suite12345", "doble12345", "simple1234",
})


def _maxmem(n: int, r: int) -> int:
    return max(64 * 1024 * 1024, 128 * n * r * 2 + 1024 * 1024)


def hash_password(password: str, n: int, r: int, p: int) -> str:
    salt = secrets.token_bytes(16)
    with _HASH_SEMAPHORE:
        digest = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=n, r=r, p=p,
            dklen=64, maxmem=_maxmem(n, r),
        )
    return "scrypt${}${}${}${}${}".format(
        n, r, p,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        scheme, n_raw, r_raw, p_raw, salt_b64, hash_b64 = encoded.split("$")
        if scheme != "scrypt":
            return False
        n, r, p = int(n_raw), int(r_raw), int(p_raw)
        salt = base64.b64decode(salt_b64, validate=True)
        expected = base64.b64decode(hash_b64, validate=True)
        with _HASH_SEMAPHORE:
            actual = hashlib.scrypt(
                password.encode("utf-8"), salt=salt, n=n, r=r, p=p,
                dklen=len(expected), maxmem=_maxmem(n, r),
            )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, binascii.Error):
        return False


@lru_cache(maxsize=8)
def fake_hash(n: int, r: int, p: int) -> str:
    """Hash ficticio para igualar el coste cuando el usuario no existe."""
    return hash_password(secrets.token_urlsafe(32), n, r, p)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def validate_password(password: str, name: str, email: str) -> None:
    if not isinstance(password, str) or not 10 <= len(password) <= 128:
        raise WeakPassword("la contraseña debe tener entre 10 y 128 caracteres")
    low = password.lower()
    if (low in COMMON_PASSWORDS
            or low == (name or "").strip().lower()
            or low == (email or "").strip().lower()):
        raise WeakPassword("elige una contraseña menos predecible")
