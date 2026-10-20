import pathlib
import subprocess

import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def load_env() -> dict:
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


ENV = load_env()
DEV_PORT = ENV.get("POSTGRES_DEV_PORT", "5433")
ADMIN_PASSWORD = ENV.get("POSTGRES_PASSWORD", "")


def dsn(dbname: str = "postgres", user: str = "postgres", password: str = None) -> str:
    return (
        f"host=127.0.0.1 port={DEV_PORT} dbname={dbname} "
        f"user={user} password={password if password is not None else ADMIN_PASSWORD}"
    )


def run_compose(args: list) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="session")
def admin_conn():
    with psycopg.connect(dsn(), autocommit=True) as conn:
        yield conn
