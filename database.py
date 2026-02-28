import os
from datetime import datetime

from sqlalchemy import BigInteger, Integer, Float, DateTime, Boolean
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, Mapped, mapped_column

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set!")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://",
        "postgresql+asyncpg://",
        1
    )
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://",
        "postgresql+asyncpg://",
        1
    )

engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)

    energy: Mapped[float] = mapped_column(Float, default=100)
    max_energy: Mapped[int] = mapped_column(Integer, default=100)
    tap_power: Mapped[int] = mapped_column(Integer, default=1)
    energy_regen: Mapped[float] = mapped_column(Float, default=1)

    auto_farm_level: Mapped[int] = mapped_column(Integer, default=0)
    auto_farm_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    last_energy_update: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    last_farm_update: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    
