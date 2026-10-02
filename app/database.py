import os
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

raw_url = os.getenv("DATABASE_URL")
if not raw_url:
    raise RuntimeError("DATABASE_URL не задан")


def _prepare_asyncpg_url(url: str) -> tuple[str, dict]:
    """
    Neon отдаёт URL вида:
      postgresql://user:pass@host/db?sslmode=require&channel_binding=require

    asyncpg НЕ понимает 'sslmode' и 'channel_binding' как query-параметры.
    Поэтому:
      - убираем их из URL
      - SSL включаем через connect_args={'ssl': ...}
    """
    # sqlalchemy нужен asyncpg-драйвер
    url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    # вырезаем параметры, которые asyncpg не понимает
    sslmode = query.pop("sslmode", ["require"])[0]
    query.pop("channel_binding", None)

    clean_query = urlencode({k: v[0] for k, v in query.items()})
    clean_url = urlunparse(parsed._replace(query=clean_query))

    # SSL для asyncpg: True = дефолтный проверяющий контекст
    ssl_arg = True if sslmode in ("require", "verify-ca", "verify-full") else False

    return clean_url, {"ssl": ssl_arg}


DATABASE_URL, SSL_CONNECT_ARGS = _prepare_asyncpg_url(raw_url)

from sqlalchemy.pool import NullPool

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    # NullPool: новое соединение на каждый запрос, никакого пула.
    # Это обходит проблему с Neon pooler, который рвёт «мёртвые» соединени.
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