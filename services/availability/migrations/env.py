import os

from alembic import context
from sqlalchemy import create_engine, pool


def get_url() -> str:
    host = os.environ.get("DB_HOST", "127.0.0.1")
    port = os.environ.get("DB_PORT", "5433")
    user = os.environ.get("DB_USER", "availability")
    password = os.environ.get("DB_PASSWORD", "")
    db = os.environ.get("DB_NAME", "availability_db")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"


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
