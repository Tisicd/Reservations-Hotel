import pytest

from app.errors import WeakPassword
from app.security import (
    fake_hash,
    hash_password,
    hash_token,
    validate_password,
    verify_password,
)

N, R, P = 1024, 8, 1


def test_hash_verify_roundtrip_y_parametros_autodescriptivos():
    encoded = hash_password("Reserva-UCE-2026!", N, R, P)
    assert encoded.startswith(f"scrypt${N}${R}${P}$")
    assert verify_password("Reserva-UCE-2026!", encoded) is True
    assert verify_password("otra", encoded) is False


def test_salt_aleatorio_cambia_el_hash():
    first = hash_password("Reserva-UCE-2026!", N, R, P)
    second = hash_password("Reserva-UCE-2026!", N, R, P)
    assert first != second
    assert verify_password("Reserva-UCE-2026!", first)
    assert verify_password("Reserva-UCE-2026!", second)


def test_formato_invalido_no_revienta():
    assert verify_password("x", "no-es-un-hash") is False
    assert verify_password("x", None) is False
    assert verify_password("x", "scrypt$x$y$z$a$b") is False


@pytest.mark.parametrize("password", [
    "corta", "1234567890", "password123", "demo123456",
])
def test_politica_rechaza_debiles(password):
    with pytest.raises(WeakPassword):
        validate_password(password, "Ana", "ana@example.com")


def test_politica_rechaza_igual_al_email_o_nombre():
    with pytest.raises(WeakPassword):
        validate_password("ana reservas uce", "Ana Reservas UCE",
                          "ana@example.com")
    with pytest.raises(WeakPassword):
        validate_password("ana@example.com", "Ana", "ana@example.com")


def test_politica_acepta_fuerte():
    validate_password("Reserva-UCE-2026!", "Ana", "ana@example.com")


def test_fake_hash_tiene_mismo_formato_y_no_valida():
    encoded = fake_hash(N, R, P)
    assert encoded.startswith(f"scrypt${N}${R}${P}$")
    assert verify_password("Reserva-UCE-2026!", encoded) is False


def test_hash_token_es_sha256_y_no_el_token():
    token = "token-de-prueba"
    digest = hash_token(token)
    assert len(digest) == 64
    assert digest != token
    assert digest == hash_token(token)
