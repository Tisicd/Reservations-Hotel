import os
import pathlib

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

SERVICE_DIR = pathlib.Path(__file__).resolve().parents[2]
REPO_ROOT = SERVICE_DIR.parent.parent

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "5433")
DB_USER = os.environ.get("DB_USER", "reservation")
DB_NAME = os.environ.get("DB_NAME", "reservation_db")


def db_password() -> str:
    secret = REPO_ROOT / "secrets" / "reservation_db_password.txt"
    if secret.exists():
        return secret.read_text().strip()
    return os.environ.get("RESERVATION_DB_PASSWORD", "change-me")


def db_url() -> str:
    return f"postgresql+psycopg://{DB_USER}:{db_password()}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


@pytest.fixture(scope="session")
def engine():
    os.environ["DB_HOST"] = DB_HOST
    os.environ["DB_PORT"] = DB_PORT
    os.environ["DB_USER"] = DB_USER
    os.environ["DB_PASSWORD"] = db_password()
    os.environ["DB_NAME"] = DB_NAME
    cfg = Config(str(SERVICE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(SERVICE_DIR / "migrations"))
    command.upgrade(cfg, "head")
    eng = create_engine(db_url(), pool_size=10)
    yield eng
    eng.dispose()


@pytest.fixture()
def clean(engine):
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE reservations, reservation_events, outbox"))


@pytest.fixture()
def repo(engine, clean):
    from app.infrastructure.db.repository import SqlReservationRepository

    return SqlReservationRepository(engine)
