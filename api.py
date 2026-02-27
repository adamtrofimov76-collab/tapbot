from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import desc, select

from database import AsyncSessionLocal, User


app = FastAPI(title="TapBot Web API")


STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class UserPayload(BaseModel):
    user_id: int


class ActionResponse(BaseModel):
    ok: bool
    message: str
    balance: int
    energy: int
    tap_power: int
    energy_regen: float
    auto_farm_level: int
    costs: dict[str, int]


async def update_energy(user: User):
    now = datetime.utcnow()
    seconds = (now - user.last_energy_update).total_seconds()
    regen = seconds * user.energy_regen
    user.energy = min(user.max_energy, user.energy + regen)
    user.last_energy_update = now


async def update_auto_farm(user: User):
    if not user.auto_farm_enabled or user.auto_farm_level == 0:
        return

    now = datetime.utcnow()
    seconds = (now - user.last_farm_update).total_seconds()
    earned = int(seconds * user.auto_farm_level)
    user.balance += earned
    user.last_farm_update = now


def get_costs(user: User) -> dict[str, int]:
    return {
        "tap_upgrade": user.tap_power * 100,
        "regen_upgrade": int(user.energy_regen * 200),
        "auto_farm_upgrade": (user.auto_farm_level + 1) * 500,
        "buy_energy": 200,
    }


def as_response(user: User, message: str) -> ActionResponse:
    return ActionResponse(
        ok=True,
        message=message,
        balance=user.balance,
        energy=int(user.energy),
        tap_power=user.tap_power,
        energy_regen=user.energy_regen,
        auto_farm_level=user.auto_farm_level,
        costs=get_costs(user),
    )


async def get_or_create_user(user_id: int) -> User:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(user_id=user_id)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return user


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/profile", response_model=ActionResponse)
async def profile(payload: UserPayload):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == payload.user_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(user_id=payload.user_id)
            session.add(user)

        await update_energy(user)
        await update_auto_farm(user)
        await session.commit()
        return as_response(user, "Профиль обновлен")


@app.post("/api/tap", response_model=ActionResponse)
async def tap(payload: UserPayload):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == payload.user_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(user_id=payload.user_id)
            session.add(user)

        await update_energy(user)
        await update_auto_farm(user)

        if user.energy < user.tap_power:
            raise HTTPException(status_code=400, detail="Нет энергии")

        user.energy -= user.tap_power
        user.balance += user.tap_power
        await session.commit()
        return as_response(user, "Тап выполнен")


@app.post("/api/upgrade/tap", response_model=ActionResponse)
async def upgrade_tap(payload: UserPayload):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == payload.user_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(user_id=payload.user_id)
            session.add(user)

        cost = user.tap_power * 100
        if user.balance < cost:
            raise HTTPException(status_code=400, detail=f"Нужно {cost} монет")

        user.balance -= cost
        user.tap_power += 1
        await session.commit()
        return as_response(user, f"Tap power: {user.tap_power}")


@app.post("/api/upgrade/regen", response_model=ActionResponse)
async def upgrade_regen(payload: UserPayload):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == payload.user_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(user_id=payload.user_id)
            session.add(user)

        cost = int(user.energy_regen * 200)
        if user.balance < cost:
            raise HTTPException(status_code=400, detail=f"Нужно {cost} монет")

        user.balance -= cost
        user.energy_regen += 0.5
        await session.commit()
        return as_response(user, f"Реген: {user.energy_regen}/сек")


@app.post("/api/upgrade/auto-farm", response_model=ActionResponse)
async def upgrade_auto_farm(payload: UserPayload):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == payload.user_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(user_id=payload.user_id)
            session.add(user)

        cost = (user.auto_farm_level + 1) * 500
        if user.balance < cost:
            raise HTTPException(status_code=400, detail=f"Нужно {cost} монет")

        user.balance -= cost
        user.auto_farm_level += 1
        user.auto_farm_enabled = True
        await session.commit()
        return as_response(user, f"Авто-фарм: {user.auto_farm_level}/сек")


@app.post("/api/buy-energy", response_model=ActionResponse)
async def buy_energy(payload: UserPayload):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == payload.user_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(user_id=payload.user_id)
            session.add(user)

        cost = 200
        if user.balance < cost:
            raise HTTPException(status_code=400, detail="Недостаточно денег")

        user.balance -= cost
        user.energy = user.max_energy
        await session.commit()
        return as_response(user, "Энергия восстановлена")


@app.get("/api/top/{kind}")
async def top(kind: str):
    mapping = {
        "balance": User.balance,
        "auto-farm": User.auto_farm_level,
        "regen": User.energy_regen,
    }

    if kind not in mapping:
        raise HTTPException(status_code=404, detail="unknown top kind")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).order_by(desc(mapping[kind])).limit(5))
        users = result.scalars().all()

    return {
        "kind": kind,
        "items": [
            {
                "user_id": u.user_id,
                "balance": u.balance,
                "auto_farm_level": u.auto_farm_level,
                "energy_regen": u.energy_regen,
            }
            for u in users
        ],
    }
