import asyncio
import datetime
import os

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command

from sqlalchemy import select
from database import SessionLocal, engine
from models import Base, User

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ---------- КНОПКИ ----------
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👆 Тап")],
        [KeyboardButton(text="⚡ Улучшить тап"),
         KeyboardButton(text="🚀 Улучшить реген")],
        [KeyboardButton(text="🔋 Купить энергию"),
         KeyboardButton(text="📊 Профиль")]
    ],
    resize_keyboard=True
)

# ---------- ВОССТАНОВЛЕНИЕ ЭНЕРГИИ ----------
def restore_energy(user):
    now = datetime.datetime.utcnow()
    seconds = (now - user.last_energy_update).total_seconds()

    if seconds <= 0:
        return

    restored = seconds * user.energy_regen

    if restored > 0:
        user.energy = min(user.max_energy, user.energy + restored)
        user.last_energy_update = now

# ---------- СТАРТ ----------
@dp.message(Command("start"))
async def start(message: types.Message):
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            user = User(user_id=message.from_user.id)
            session.add(user)
            await session.commit()

    await message.answer("🔥 Добро пожаловать в TAP GAME!", reply_markup=keyboard)

# ---------- ТАП ----------
@dp.message(lambda m: m.text == "👆 Тап")
async def tap(message: types.Message):
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one()

        restore_energy(user)

if user.energy >= 1:
    user.energy -= 1
    user.balance += user.tap_power
    user.xp += 1
    await session.commit()
    await message.answer(f"+{user.tap_power} очков 💰")
else:
    await session.commit()  # ← ВОТ ЭТУ СТРОКУ ДОБАВИТЬ
    await message.answer("❌ Нет энергии!")

# ---------- ПРОФИЛЬ ----------
@dp.message(lambda m: m.text == "📊 Профиль")
async def profile(message: types.Message):
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one()

        restore_energy(user)
        await session.commit()

        text = (
            f"💰 Баланс: {user.balance}\n"
            f"⚡ Энергия: {round(user.energy,1)}/{user.max_energy}\n"
            f"👆 Тап: {user.tap_power}\n"
            f"🚀 Реген: {user.energy_regen}/сек\n"
        )

        await message.answer(text)

# ---------- УЛУЧШЕНИЕ ТАПА ----------
@dp.message(lambda m: m.text == "⚡ Улучшить тап")
async def upgrade_tap(message: types.Message):
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one()

        cost = 100 * user.tap_power

        if user.balance >= cost:
            user.balance -= cost
            user.tap_power += 1
            await session.commit()
            await message.answer("✅ Тап усилен!")
        else:
            await message.answer(f"❌ Нужно {cost} очков")

# ---------- УЛУЧШЕНИЕ РЕГЕНА ----------
@dp.message(lambda m: m.text == "🚀 Улучшить реген")
async def upgrade_regen(message: types.Message):
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one()

        cost = int(200 * user.energy_regen)

        if user.balance >= cost:
            user.balance -= cost
            user.energy_regen += 0.5
            await session.commit()
            await message.answer("🚀 Реген ускорен!")
        else:
            await message.answer(f"❌ Нужно {cost} очков")

# ---------- КУПИТЬ ЭНЕРГИЮ ----------
@dp.message(lambda m: m.text == "🔋 Купить энергию")
async def buy_energy(message: types.Message):
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one()

        if user.balance >= 50:
            user.balance -= 50
            user.energy = min(user.max_energy, user.energy + 5)
            await session.commit()
            await message.answer("🔋 +5 энергии")
        else:
            await message.answer("❌ Нужно 50 очков")

# ---------- ЗАПУСК ----------
async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())