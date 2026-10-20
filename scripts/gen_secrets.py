import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SECRETS_DIR = ROOT / "secrets"

# nombre de archivo en secrets/ -> clave en .env
MAPPING = {
    "customer_db_password.txt": "CUSTOMER_DB_PASSWORD",
    "hotel_db_password.txt": "HOTEL_DB_PASSWORD",
    "availability_db_password.txt": "AVAILABILITY_DB_PASSWORD",
    "payment_db_password.txt": "PAYMENT_DB_PASSWORD",
    "reservation_db_password.txt": "RESERVATION_DB_PASSWORD",
}


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    p = ROOT / ".env"
    if not p.exists():
        return env
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def main() -> None:
    env = load_env()
    SECRETS_DIR.mkdir(exist_ok=True)
    for filename, key in MAPPING.items():
        value = env.get(key)
        if not value:
            raise SystemExit(f"Falta {key} en .env")
        (SECRETS_DIR / filename).write_text(value + "\n")
    print(f"secretos generados en {SECRETS_DIR}")


if __name__ == "__main__":
    main()
