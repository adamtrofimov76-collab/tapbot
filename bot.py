import asyncio
import json
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.getenv("BOT_TOKEN")
print("TOKEN:", TOKEN)

bot = Bot(token=TOKEN)
dp = Dispatcher()

try:
    with open("data.json", "r") as f:
        users = json.load(f)
except:
    users = {}

def save():
    with open("data.json", "w") as f:
        json.dump(users, f)

def get_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💥 TAP", callback_data="tap")],
        [InlineKeyboardButton(text="📊 Профиль", callback_data="profile")]
    ])

@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = str(message.from_user.id)

    if user_id not in users:
        users[user_id] = {"score": 0, "energy": 100}
        save()

    await message.answer("🔥 Добро пожаловать в TAP GAME!", reply_markup=get_keyboard())

@dp.callback_query()
async def callbacks(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)

    if callback.data == "tap":
        if users[user_id]["energy"] > 0:
            users[user_id]["score"] += 1
            users[user_id]["energy"] -= 1
            save()

        await callback.message.edit_text(
            f"💰 Очки: {users[user_id]['score']}\n⚡ Энергия: {users[user_id]['energy']}",
            reply_markup=get_keyboard()
        )

    elif callback.data == "profile":
        await callback.answer(
            f"💰 Очки: {users[user_id]['score']}\n⚡ Энергия: {users[user_id]['energy']}",
            show_alert=True
        )

async def main():
    print("Bot started 🚀")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())