import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from sqlalchemy import select

import os
from database import AsyncSessionLocal, User


BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_VERSION = os.getenv("RAILWAY_GIT_COMMIT_SHA", "local")[:7]

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()


def get_tap_upgrade_cost(user: User) -> int:
    return user.tap_power * 100


def get_regen_upgrade_cost(user: User) -> int:
    return int(user.energy_regen * 200)


def get_auto_farm_upgrade_cost(user: User) -> int:
    return (user.auto_farm_level + 1) * 500


def build_keyboard(user: User) -> ReplyKeyboardMarkup:
    tap_cost = get_tap_upgrade_cost(user)
    regen_cost = get_regen_upgrade_cost(user)
    auto_farm_cost = get_auto_farm_upgrade_cost(user)

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👇 Тап")],
            [KeyboardButton(text=f"⚡ Улучшить тап • {tap_cost}💰")],
            [KeyboardButton(text=f"🚀 Улучшить реген • {regen_cost}💰")],
            [KeyboardButton(text="💵 Купить энергию • 200💰")],
            [KeyboardButton(text=f"🤖 Авто-фарм • {auto_farm_cost}💰")],
            [KeyboardButton(text="📊 Профиль")],
            [KeyboardButton(text="🔄 Обновить клавиатуру")],
        ],
        resize_keyboard=True,
    )


async def send_with_fresh_keyboard(message: Message, text: str, user: User):
    # Принудительно сбрасываем старую клавиатуру, чтобы Telegram-клиент точно принял новую разметку
    await message.answer("🔄 Обновляю клавиатуру...", reply_markup=ReplyKeyboardRemove())
    await message.answer(text, reply_markup=build_keyboard(user))


# -------- ЭНЕРГИЯ --------
async def update_energy(user: User):
    now = datetime.utcnow()
    seconds = (now - user.last_energy_update).total_seconds()

    regen = seconds * user.energy_regen
    user.energy = min(user.max_energy, user.energy + regen)
    user.last_energy_update = now


# -------- АВТОФАРМ --------
async def update_auto_farm(user: User):
    if not user.auto_farm_enabled or user.auto_farm_level == 0:
        return

    now = datetime.utcnow()
    seconds = (now - user.last_farm_update).total_seconds()

    earned = int(seconds * user.auto_farm_level)
    user.balance += earned
    user.last_farm_update = now


# -------- START --------
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

        await send_with_fresh_keyboard(
            message,
            f"🔥 Добро пожаловать!\n\n"
            f"💰 Баланс: {user.balance}\n"
            f"⚡ Энергия: {int(user.energy)}\n"
            f"🧩 Версия: {APP_VERSION}",
            user,
        )


# -------- ТАП --------
@dp.message(F.text == "👇 Тап")
async def tap_handler(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one()

        await update_energy(user)
        await update_auto_farm(user)

        if user.energy < user.tap_power:
            await message.answer("❌ Нет энергии!", reply_markup=build_keyboard(user))
            return

        user.energy -= user.tap_power
        user.balance += user.tap_power

        await session.commit()

        await message.answer(
            f"💰 Баланс: {user.balance}\n"
            f"⚡ Энергия: {int(user.energy)}\n"
            f"🧩 Версия: {APP_VERSION}",
            reply_markup=build_keyboard(user),
        )


# -------- УЛУЧШЕНИЯ --------
@dp.message(F.text.startswith("⚡ Улучшить тап") | F.text.startswith("⚡ Тап +1"))
async def upgrade_tap(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one()

        cost = get_tap_upgrade_cost(user)

        if user.balance < cost:
            await message.answer("❌ Недостаточно денег!", reply_markup=build_keyboard(user))
            return

        user.balance -= cost
        user.tap_power += 1
        await session.commit()

        await message.answer(
            f"⚡ Tap power теперь: {user.tap_power}",
            reply_markup=build_keyboard(user),
        )


@dp.message(F.text.startswith("🚀 Улучшить реген") | F.text.startswith("🚀 Реген +0.5"))
async def upgrade_regen(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one()

        cost = get_regen_upgrade_cost(user)

        if user.balance < cost:
            await message.answer("❌ Недостаточно денег!", reply_markup=build_keyboard(user))
            return

        user.balance -= cost
        user.energy_regen += 0.5
        await session.commit()

        await message.answer(
            f"🚀 Реген теперь: {user.energy_regen}/сек",
            reply_markup=build_keyboard(user),
        )


@dp.message(F.text.startswith("💵 Купить энергию") | F.text.startswith("💵 Энергия"))
async def buy_energy(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one()

        cost = 200

        if user.balance < cost:
            await message.answer("❌ Недостаточно денег!", reply_markup=build_keyboard(user))
            return

        user.balance -= cost
        user.energy = user.max_energy
        await session.commit()

        await message.answer("⚡ Энергия восстановлена!", reply_markup=build_keyboard(user))


@dp.message(F.text.startswith("🤖 Авто-фарм") | F.text.startswith("🤖 Авто-фарм +1"))
async def auto_farm(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one()

        cost = get_auto_farm_upgrade_cost(user)

        if user.balance < cost:
            await message.answer(f"❌ Нужно {cost} монет", reply_markup=build_keyboard(user))
            return

        user.balance -= cost
        user.auto_farm_level += 1
        user.auto_farm_enabled = True

        await session.commit()

        await message.answer(
            f"🤖 Авто-фарм уровень: {user.auto_farm_level}\n"
            f"Фармит {user.auto_farm_level} монет/сек",
            reply_markup=build_keyboard(user),
        )


@dp.message(F.text == "🔄 Обновить клавиатуру")
async def refresh_keyboard(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one()

        await update_energy(user)
        await update_auto_farm(user)
        await session.commit()

        await send_with_fresh_keyboard(
            message,
            "✅ Клавиатура обновлена.",
            user,
        )


@dp.message(F.text == "📊 Профиль")
async def profile(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one()

        await update_energy(user)
        await update_auto_farm(user)
        await session.commit()

        await send_with_fresh_keyboard(
            message,
            f"📊 Профиль\n\n"
            f"💰 Баланс: {user.balance}\n"
            f"⚡ Энергия: {int(user.energy)}\n"
            f"⚡ Tap power: {user.tap_power}\n"
            f"🚀 Реген: {user.energy_regen}/сек\n"
            f"🤖 Авто-фарм: {user.auto_farm_level}/сек",
            user,
        )


@dp.message(Command("version"))
@dp.message(F.text.regexp(r"^/version(@[A-Za-z0-9_]+)?$"))
@dp.message(F.text.in_(["version", "Version", "версия", "Версия"]))
async def version_handler(message: Message):
    await message.answer(
        "ℹ️ Версия бота\n"
        f"🧩 commit: {APP_VERSION}\n\n"
        "Если кнопки не меняются после /start — значит в Railway крутится старый деплой. "
        "Сделайте Redeploy последнего коммита и проверьте /version снова."
    )


async def main():
    from database import Base, engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print(f"[tapbot] starting version={APP_VERSION}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
