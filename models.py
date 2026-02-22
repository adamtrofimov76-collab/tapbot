from sqlalchemy import Column, BigInteger, Integer, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)

    balance = Column(Integer, default=0)

    tap_power = Column(Integer, default=1)

    auto_click = Column(Integer, default=0)

    last_update = Column(DateTime, default=datetime.utcnow)
