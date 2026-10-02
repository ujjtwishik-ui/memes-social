import os
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv

load_dotenv()

raw_url = os.getenv("DATABASE_URL")
if not raw_url:
    raise RuntimeError("DATABASE_URL не задан")


def _prepare_asyncpg_url(url: str):
    """Neon отдаёт URL с sslmode/channel_binding, которые asyncpg не понимает.
    Вырезаем их, SSL включаем через connect_args."""
    url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    sslmode = query.pop("sslmode", ["require"])[0]
    query.pop("channel_binding", None)
    clean_query = urlencode({k: v[0] for k, v in query.items()})
    clean_url = urlunparse(parsed._replace(query=clean_query))
    ssl_arg = True if sslmode in ("require", "verify-ca", "verify-full") else False
    return clean_url, {"ssl": ssl_arg}


DATABASE_URL, SSL_CONNECT_ARGS = _prepare_asyncpg_url(raw_url)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    poolclass=NullPool,
    connect_args={
        **SSL_CONNECT_ARGS,
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "server_settings": {
            "application_name": "memes-social",
            "jit": "off",
        },
    },
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()