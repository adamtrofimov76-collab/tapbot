import os
import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart

from sqlalchemy import Column, BigInteger, Integer, DateTime, select
from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession
)
from sqlalchemy.orm import sessionmaker


# ========================
# НАСТРОЙКИ
# ========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://",
        "postgresql+asyncpg://"
    )


# ========================
# БАЗА ДАННЫХ
# ========================

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)

    balance = Column(Integer, default=0)

    tap_power = Column(Integer, default=1)

    auto_click = Column(Integer, default=0)

    last_update = Column(DateTime, default=datetime.utcnow)


engine = create_async_engine(DATABASE_URL, echo=False)

SessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ========================
# ЛОГИКА
# ========================

async def get_user(session, user_id: int):
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        user = User(id=user_id)
        session.add(user)
        await session.commit()

    return user


async def update_balance(user: User):
    now = datetime.utcnow()
    seconds_passed = (now - user.last_update).total_seconds()

    earned = int(seconds_passed * user.auto_click)

    user.balance += earned
    user.last_update = now


# ========================
# БОТ
# ========================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# Клавиатура
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👆 Тап")],
        [KeyboardButton(text="🚀 Купить автоклик")],
        [KeyboardButton(text="📊 Профиль")]
    ],
    resize_keyboard=True
)


# ========================
# ХЕНДЛЕРЫ
# ========================

@dp.message(CommandStart())
async def start(message: Message):
    async with SessionLocal() as session:
        user = await get_user(session, message.from_user.id)
        await update_balance(user)
        await session.commit()

        await message.answer(
            "🔥 Добро пожаловать в TAP GAME!\n\n"
            "Зарабатывай монеты 👇",
            reply_markup=main_kb
        )


@dp.message(F.text == "👆 Тап")
async def tap(message: Message):
    async with SessionLocal() as session:
        user = await get_user(session, message.from_user.id)

        await update_balance(user)

        user.balance += user.tap_power

        await session.commit()

        await message.answer(f"💰 Баланс: {user.balance}")


@dp.message(F.text == "🚀 Купить автоклик")
async def buy_auto(message: Message):
    async with SessionLocal() as session:
        user = await get_user(session, message.from_user.id)

        await update_balance(user)

        cost = 100 + (user.auto_click * 50)

        if user.balance >= cost:
            user.balance -= cost
            user.auto_click += 1
            await session.commit()

            await message.answer(
                f"✅ Автоклик улучшен!\n"
                f"Теперь: {user.auto_click} монет/сек\n"
                f"💰 Баланс: {user.balance}"
            )
        else:
            await message.answer(
                f"❌ Нужно {cost} монет\n"
                f"💰 Баланс: {user.balance}"
            )


@dp.message(F.text == "📊 Профиль")
async def profile(message: Message):
    async with SessionLocal() as session:
        user = await get_user(session, message.from_user.id)

        await update_balance(user)
        await session.commit()

        await message.answer(
            f"📊 Профиль\n\n"
            f"💰 Баланс: {user.balance}\n"
            f"👆 Сила тапа: {user.tap_power}\n"
            f"⚡ Автоклик: {user.auto_click}/сек"
        )


# ========================
# ЗАПУСК
# ========================

async def main():
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
