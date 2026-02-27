import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from sqlalchemy import select, desc

import os
from database import AsyncSessionLocal, User


BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_VERSION = os.getenv("RAILWAY_GIT_COMMIT_SHA", "local")[:7]
GAME_VERSION = "0.0.1"

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

# user_id -> bot status message_id (for edit on tap)
last_status_message_ids: dict[int, int] = {}


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
            [KeyboardButton(text="🏆 Рейтинг")],
            [KeyboardButton(text="📊 Профиль")],
        ],
        resize_keyboard=True,
    )




def build_rating_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Топ по балансу")],
            [KeyboardButton(text="🤖 Топ по авто-фарму")],
            [KeyboardButton(text="🚀 Топ по регену")],
            [KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True,
    )

async def send_with_fresh_keyboard(message: Message, text: str, user: User) -> Message:
    # Принудительно сбрасываем старую клавиатуру, чтобы Telegram-клиент точно принял новую разметку
    await message.answer("🔄 Обновляю клавиатуру...", reply_markup=ReplyKeyboardRemove())
    sent = await message.answer(text, reply_markup=build_keyboard(user))
    return sent


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


def build_status_text(user: User) -> str:
    return (
        f"💰 Баланс: {user.balance}\n"
        f"⚡ Энергия: {int(user.energy)}\n"
        f"🎮 Версия игры: {GAME_VERSION}"
    )


async def upsert_status_message(message: Message, user: User, prefix: str | None = None):
    text = build_status_text(user)
    if prefix:
        text = f"{prefix}\n\n{text}"

    cached_message_id = last_status_message_ids.get(user.user_id)

    if cached_message_id is not None:
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=cached_message_id,
                text=text,
                reply_markup=build_keyboard(user),
            )
            return
        except Exception:
            pass

    sent = await message.answer(text, reply_markup=build_keyboard(user))
    last_status_message_ids[user.user_id] = sent.message_id




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

        tg_name = message.from_user.first_name or message.from_user.username or "фермер"

        sent = await send_with_fresh_keyboard(
            message,
            f"👋 Привет, {tg_name}!\n"
            f"Ты попал на ферму, тут тебе надо усердно кликать и прокачивать свой огород.\n"
            f"Стань самым богатым фермером в нашей игре!\n\n"
            f"💰 Баланс: {user.balance}\n"
            f"⚡ Энергия: {int(user.energy)}\n"
            f"🎮 Версия игры: {GAME_VERSION}",
            user,
        )
        last_status_message_ids[user.user_id] = sent.message_id


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
            await upsert_status_message(message, user, prefix="❌ Нет энергии!")
            return

        user.energy -= user.tap_power
        user.balance += user.tap_power

        await session.commit()

        await upsert_status_message(message, user)


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
            await upsert_status_message(message, user, prefix="❌ Недостаточно денег!")
            return

        user.balance -= cost
        user.tap_power += 1
        await session.commit()

        await upsert_status_message(message, user, prefix=f"⚡ Tap power теперь: {user.tap_power}")


@dp.message(F.text.startswith("🚀 Улучшить реген") | F.text.startswith("🚀 Реген +0.5"))
async def upgrade_regen(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one()

        cost = get_regen_upgrade_cost(user)

        if user.balance < cost:
            await upsert_status_message(message, user, prefix="❌ Недостаточно денег!")
            return

        user.balance -= cost
        user.energy_regen += 0.5
        await session.commit()

        await upsert_status_message(message, user, prefix=f"🚀 Реген теперь: {user.energy_regen}/сек")


@dp.message(F.text.startswith("💵 Купить энергию") | F.text.startswith("💵 Энергия"))
async def buy_energy(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one()

        cost = 200

        if user.balance < cost:
            await upsert_status_message(message, user, prefix="❌ Недостаточно денег!")
            return

        user.balance -= cost
        user.energy = user.max_energy
        await session.commit()

        await upsert_status_message(message, user, prefix="⚡ Энергия восстановлена!")


@dp.message(F.text.startswith("🤖 Авто-фарм") | F.text.startswith("🤖 Авто-фарм +1"))
async def auto_farm(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one()

        cost = get_auto_farm_upgrade_cost(user)

        if user.balance < cost:
            await upsert_status_message(message, user, prefix=f"❌ Нужно {cost} монет")
            return

        user.balance -= cost
        user.auto_farm_level += 1
        user.auto_farm_enabled = True

        await session.commit()

        await upsert_status_message(
            message,
            user,
            prefix=(
                f"🤖 Авто-фарм уровень: {user.auto_farm_level}\n"
                f"Фармит {user.auto_farm_level} монет/сек"
            ),
        )


@dp.message(F.text == "🏆 Рейтинг")
async def rating_menu(message: Message):
    await message.answer("🏆 Рейтинг\nВыбери категорию топ-5:", reply_markup=build_rating_keyboard())


@dp.message(F.text == "⬅️ Назад")
async def rating_back(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == message.from_user.id)
        )
        user = result.scalar_one()

        await message.answer("↩️ Вернул в главное меню", reply_markup=build_keyboard(user))


async def format_top_lines(users: list[User], value_getter) -> str:
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    lines: list[str] = []

    for i, u in enumerate(users):
        user_label = f"id{u.user_id}"
        try:
            chat = await bot.get_chat(u.user_id)
            if chat.username:
                user_label = f"@{chat.username}"
            elif chat.first_name:
                user_label = chat.first_name
        except Exception:
            pass

        lines.append(f"{medals[i]} {user_label} — {value_getter(u)}")

    return "\n".join(lines) if lines else "Пока нет данных"


@dp.message(F.text == "💰 Топ по балансу")
async def top_balance(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).order_by(desc(User.balance)).limit(5)
        )
        users = result.scalars().all()

        lines = await format_top_lines(users, lambda u: f"{u.balance} 💰")
        await message.answer(
            f"💰 <b>Топ-5 по балансу</b>\n\n{lines}",
            reply_markup=build_rating_keyboard(),
        )


@dp.message(F.text == "🤖 Топ по авто-фарму")
async def top_auto_farm(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).order_by(desc(User.auto_farm_level)).limit(5)
        )
        users = result.scalars().all()

        lines = await format_top_lines(users, lambda u: f"{u.auto_farm_level}/сек")
        await message.answer(
            f"🤖 <b>Топ-5 по авто-фарму</b>\n\n{lines}",
            reply_markup=build_rating_keyboard(),
        )


@dp.message(F.text == "🚀 Топ по регену")
async def top_regen(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).order_by(desc(User.energy_regen)).limit(5)
        )
        users = result.scalars().all()

        lines = await format_top_lines(users, lambda u: f"{u.energy_regen}/сек")
        await message.answer(
            f"🚀 <b>Топ-5 по регену</b>\n\n{lines}",
            reply_markup=build_rating_keyboard(),
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
        "ℹ️ Версия игры и деплоя\n"
        f"🎮 game: {GAME_VERSION}\n"
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
