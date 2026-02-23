import os
import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

from sqlalchemy import select
from database import AsyncSessionLocal, User


BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()


# -----------------------
# 🔋 Реген энергии
# -----------------------
async def regenerate_energy(user: User):
    now = datetime.utcnow()
    delta = (now - user.last_energy_update).total_seconds()

    regen_amount = delta * user.energy_regen

    if regen_amount > 0:
        user.energy = min(user.max_energy, user.energy + regen_amount)
        user.last_energy_update = now


# -----------------------
# 🚀 /start
# -----------------------
@dp.message(Command("start"))
async def start_handler(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            user = User(user_id=message.from_user.id)
            session.add(user)
            await session.commit()

    await message.answer(
        "🔥 Добро пожаловать в TAP GAME!\n\n"
        "Используй команды:\n"
        "/tap — фармить\n"
        "/profile — профиль"
    )


# -----------------------
# 👆 Тап
# -----------------------
@dp.message(Command("tap"))
async def tap_handler(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("Сначала используй /start")
            return

        await regenerate_energy(user)

        if user.energy < 1:
            await message.answer("⚡ Недостаточно энергии!")
            return

        user.energy -= 1
        user.balance += user.tap_power
        user.xp += 1

        await session.commit()

        await message.answer(
            f"👆 +{user.tap_power} монет\n"
            f"💰 Баланс: {user.balance}\n"
            f"⚡ Энергия: {int(user.energy)}/{user.max_energy}"
        )


# -----------------------
# 👤 Профиль
# -----------------------
@dp.message(Command("profile"))
async def profile_handler(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("Сначала используй /start")
            return

        await regenerate_energy(user)
        await session.commit()

        await message.answer(
            f"👤 Профиль\n\n"
            f"💰 Баланс: {user.balance}\n"
            f"⚡ Энергия: {int(user.energy)}/{user.max_energy}\n"
            f"🔥 Сила тапа: {user.tap_power}\n"
            f"⭐ XP: {user.xp}\n"
            f"🏆 Уровень: {user.level}"
        )


# -----------------------
# ▶ Запуск
# -----------------------
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
