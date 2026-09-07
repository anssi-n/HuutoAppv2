from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text
import psycopg
from typing import AsyncGenerator
from config import settings
from pathlib import Path
import aiofiles

class Base(DeclarativeBase):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
CREDS_DIR = Path(settings.database_credential_dir)

async def get_db_credentials_async() -> tuple[str, str]:
    async with aiofiles.open((CREDS_DIR / "username"), mode='r', encoding='utf-8') as f:
        username = await f.read()
    async with aiofiles.open((CREDS_DIR / "password"), mode='r', encoding='utf-8') as f:
        password = await f.read()
    return str(username).strip(), str(password).strip()

def get_db_credentials() -> tuple[str, str]:
    username = (CREDS_DIR / "username").read_text().strip()
    password = (CREDS_DIR / "password").read_text().strip()
    return username, password

async def async_connect_with_dynamic_creds():
    username, password = await get_db_credentials_async()
    return await psycopg.AsyncConnection.connect(
        conninfo=f"host={settings.database_host} dbname={settings.database_name}",
        user=username,
        password=password
    )    

def connect_with_dynamic_creds():
    username, password = get_db_credentials()
    return psycopg.Connection.connect(
        conninfo=f"host={settings.database_host} dbname={settings.database_name}",
        user=username,
        password=password
    )    

engine = create_async_engine(
    "postgresql+psycopg://", 
    async_creator=async_connect_with_dynamic_creds,
    pool_recycle=300,
    pool_pre_ping=True
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

sync_engine = create_engine(
    "postgresql+psycopg://", 
    creator=connect_with_dynamic_creds,
    pool_recycle=300,
    pool_pre_ping=True)

async def get_db() -> AsyncGenerator[AsyncSession]:
    async with AsyncSessionLocal() as db:
        yield db