from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, BigInteger, Float, DateTime
import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    user_id = Column(BigInteger, primary_key=True)

    balance = Column(Integer, default=0)

    energy = Column(Float, default=10)
    max_energy = Column(Float, default=10)

    tap_power = Column(Integer, default=1)
    energy_regen = Column(Float, default=0.5)

    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)

    last_energy_update = Column(DateTime, default=datetime.datetime.utcnow)