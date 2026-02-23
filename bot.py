import os
import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from sqlalchemy import select

from database import AsyncSessionLocal, User


BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()


# ---------- ЭНЕРГИЯ ----------

def update_energy(user: User):
    now = datetime.utcnow()
    seconds_passed = (now - user.last_energy_update).total_seconds()

    regenerated = seconds_passed * user.energy_regen
    user.energy = min(user.max_energy, user.energy + regenerated)

    user.last_energy_update = now


# ---------- /start ----------

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
            f"🔥 Добро пожаловать!\n\n"
            f"💰 Баланс: {user.balance}\n"
            f"⚡ Энергия: {int(user.energy)}"
        )


# ---------- ТАП ----------

@dp.message(F.text == "Тап")
async def tap_handler(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return

        update_energy(user)

        if user.energy < user.tap_power:
            await message.answer("❌ Недостаточно энергии!")
            return

        user.energy -= user.tap_power
        user.balance += user.tap_power
        user.xp += 1

        await session.commit()

        await message.answer(
            f"💰 Баланс: {user.balance}\n"
            f"⚡ Энергия: {int(user.energy)}"
        )


# ---------- ЗАПУСК ----------

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
