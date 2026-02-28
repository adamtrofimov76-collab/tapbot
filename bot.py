import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from sqlalchemy import select, desc

import os
from database import AsyncSessionLocal, User


BOT_TOKEN = os.getenv("BOT_TOKEN")
BLOCKED_TOP_USER_ID = 8375181976

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()


main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👇 Тап")],
        [KeyboardButton(text="🛠 Улучшения")],
        [KeyboardButton(text="🏆 Рейтинг")],
        [KeyboardButton(text="📊 Профиль")]
    ],
    resize_keyboard=True
)

upgrades_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="⚡ Улучшить тап")],
        [KeyboardButton(text="🚀 Улучшить реген")],
        [KeyboardButton(text="💵 Купить энергию")],
        [KeyboardButton(text="🤖 Авто-фарм")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True,
)

rating_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💰 Топ по балансу")],
        [KeyboardButton(text="🤖 Топ по авто-фарму")],
        [KeyboardButton(text="🚀 Топ по регену")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True,
)


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

        username = message.from_user.first_name or message.from_user.username or "фермер"

        await message.answer(
            f"👋 Добро пожаловать, {username}!\n\n"
            f"🌾 «Фермер» — это игра, где ты можешь соревноваться с друзьями и с реальными игроками, "
            f"поднимаясь в рейтинге.\n\n"
            f"💡 Нажимай на тап, прокачивай улучшения и развивай свой огород, чтобы стать самым "
            f"богатым фермером!\n\n"
            f"🤝 Приятной игры!\n"
            f"С уважением, твой Фермер.\n\n"
            f"💰 Баланс: {user.balance}\n"
            f"⚡ Энергия: {int(user.energy)}",
            reply_markup=main_keyboard
        )


@dp.message(F.text == "🛠 Улучшения")
async def upgrades_menu(message: Message):
    await message.answer("🛠 Меню улучшений", reply_markup=upgrades_keyboard)


@dp.message(F.text == "🏆 Рейтинг")
async def rating_menu(message: Message):
    await message.answer("🏆 Выбери рейтинг", reply_markup=rating_keyboard)


@dp.message(F.text == "⬅️ Назад")
async def back_to_main_menu(message: Message):
    await message.answer("⬅️ Главное меню", reply_markup=main_keyboard)


async def resolve_player_name(user_id: int) -> str:
    try:
        chat = await bot.get_chat(user_id)
    except Exception:
        return f"id{user_id}"

    if chat.username:
        return f"@{chat.username}"
    if chat.first_name:
        return chat.first_name
    return f"id{user_id}"


async def format_top(users: list[User], value_getter) -> str:
    filtered_users = [u for u in users if u.user_id != BLOCKED_TOP_USER_ID]

    if not filtered_users:
        return "Пока пусто"

    lines = []
    for i, u in enumerate(filtered_users[:5], start=1):
        name = await resolve_player_name(u.user_id)
        lines.append(f"{i}. {name} — {value_getter(u)}")
    return "\n".join(lines)


@dp.message(F.text == "💰 Топ по балансу")
async def top_balance(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).order_by(desc(User.balance)).limit(10))
        users = result.scalars().all()

    top_text = await format_top(users, lambda u: f"{u.balance}💰")
    await message.answer(f"💰 Топ-5 по балансу\n\n{top_text}", reply_markup=rating_keyboard)


@dp.message(F.text == "🤖 Топ по авто-фарму")
async def top_auto_farm(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).order_by(desc(User.auto_farm_level)).limit(10))
        users = result.scalars().all()

    top_text = await format_top(users, lambda u: f"{u.auto_farm_level}/сек")
    await message.answer(f"🤖 Топ-5 по авто-фарму\n\n{top_text}", reply_markup=rating_keyboard)


@dp.message(F.text == "🚀 Топ по регену")
async def top_regen(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).order_by(desc(User.energy_regen)).limit(10))
        users = result.scalars().all()

    top_text = await format_top(users, lambda u: f"{u.energy_regen}/сек")
    await message.answer(f"🚀 Топ-5 по регену\n\n{top_text}", reply_markup=rating_keyboard)


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
            await message.answer("❌ Нет энергии!")
            return

        user.energy -= user.tap_power
        user.balance += user.tap_power

        await session.commit()

        await message.answer(
            f"💰 Баланс: {user.balance}\n"
            f"⚡ Энергия: {int(user.energy)}"
        )


# -------- УЛУЧШЕНИЯ --------
@dp.message(F.text == "⚡ Улучшить тап")
async def upgrade_tap(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one()

        cost = user.tap_power * 100

        if user.balance < cost:
            await message.answer("❌ Недостаточно денег!")
            return

        user.balance -= cost
        user.tap_power += 1
        await session.commit()

        await message.answer(f"⚡ Tap power теперь: {user.tap_power}")


@dp.message(F.text == "🚀 Улучшить реген")
async def upgrade_regen(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one()

        cost = int(user.energy_regen * 200)

        if user.balance < cost:
            await message.answer("❌ Недостаточно денег!")
            return

        user.balance -= cost
        user.energy_regen += 0.5
        await session.commit()

        await message.answer(f"🚀 Реген теперь: {user.energy_regen}/сек")


@dp.message(F.text == "💵 Купить энергию")
async def buy_energy(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one()

        cost = 200

        if user.balance < cost:
            await message.answer("❌ Недостаточно денег!")
            return

        user.balance -= cost
        user.energy = user.max_energy
        await session.commit()

        await message.answer("⚡ Энергия восстановлена!")


@dp.message(F.text == "🤖 Авто-фарм")
async def auto_farm(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one()

        cost = (user.auto_farm_level + 1) * 500

        if user.balance < cost:
            await message.answer(f"❌ Нужно {cost} монет")
            return

        user.balance -= cost
        user.auto_farm_level += 1
        user.auto_farm_enabled = True

        await session.commit()

        await message.answer(
            f"🤖 Авто-фарм уровень: {user.auto_farm_level}\n"
            f"Фармит {user.auto_farm_level} монет/сек"
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

        await message.answer(
            f"📊 Профиль\n\n"
            f"💰 Баланс: {user.balance}\n"
            f"⚡ Энергия: {int(user.energy)}\n"
            f"⚡ Tap power: {user.tap_power}\n"
            f"🚀 Реген: {user.energy_regen}/сек\n"
            f"🤖 Авто-фарм: {user.auto_farm_level}/сек"
        )


async def main():
    from database import Base, engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
