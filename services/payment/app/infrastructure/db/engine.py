from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def make_engine(url: str, pool_size: int, pool_timeout: int) -> Engine:
    return create_engine(
        url,
        pool_size=pool_size,
        pool_timeout=pool_timeout,
        pool_pre_ping=True,
    )
