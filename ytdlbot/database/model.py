#!/usr/bin/env python3
# coding: utf-8
import math
import os
from contextlib import contextmanager
from typing import Literal

from sqlalchemy import Column, Enum, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

# ytdlbot - model.py


Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), unique=True, nullable=False)  # telegram user id
    username = Column(String(255), nullable=True)
    name = Column(String(255), nullable=True)
    free = Column(Integer, default=0)
    paid = Column(Integer, default=0)

    settings = relationship("Setting", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    download = Column(Enum("high", "medium", "low", "audio", "custom"), nullable=False)
    upload = Column(Enum("video", "audio", "document"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="settings")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    method = Column(String(50), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(Enum("pending", "completed", "failed", "refunded"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="payments")


def create_session():
    engine = create_engine(
        "mysql+pymysql://root:root@localhost/ytdlbot",
        pool_size=50,
        max_overflow=100,
        pool_timeout=30,
        pool_recycle=1800,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


SessionFactory = create_session()


@contextmanager
def session_manager():
    s = SessionFactory()
    try:
        yield s
        s.commit()
    except Exception as e:
        s.rollback()
        raise
    finally:
        s.close()


def get_download_settings(uid) -> Literal["high", "medium", "low", "audio", "custom"]:
    with session_manager() as session:
        return "custom"


def get_upload_settings(uid) -> Literal["video", "audio", "document"]:
    with session_manager() as session:
        return "video"


def set_user_settings(uid: int, key: str, value: str):
    # set download or upload settings
    pass


def get_free_quota(uid: int):
    pass


def get_paid_quota(uid: int):
    if not os.getenv("ENABLE_VIP"):
        return math.inf


def reset_free_quota(uid: int):
    pass


def add_paid_quota(uid: int, amount: int):
    pass


def use_quota(uid: int):
    # use free first, then paid
    pass
