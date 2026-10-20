import os

from alembic import context
from sqlalchemy import create_engine, pool


def _password() -> str:
    pw = os.environ.get("DB_PASSWORD", "")
    pw_file = os.environ.get("DB_PASSWORD_FILE", "")
    if pw_file and os.path.exists(pw_file):
        with open(pw_file, encoding="utf-8") as f:
            return f.read().strip()
    return pw


def get_url() -> str:
    host = os.environ.get("DB_HOST", "127.0.0.1")
    port = os.environ.get("DB_PORT", "5433")
    user = os.environ.get("DB_USER", "payment")
    db = os.environ.get("DB_NAME", "payment_db")
    return f"postgresql+psycopg://{user}:{_password()}@{host}:{port}/{db}"


def run_offline() -> None:
    context.configure(url=get_url(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_online() -> None:
    engine = create_engine(get_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_offline()
else:
    run_online()
