#!/usr/bin/env python3
# coding: utf-8
import logging
import math
import os
from contextlib import contextmanager
from typing import Literal

from sqlalchemy import (
    BigInteger,
    Column,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from config import FREE_DOWNLOAD


class PaymentStatus:
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, unique=True, nullable=False)  # telegram user id
    free = Column(Integer, default=FREE_DOWNLOAD)
    paid = Column(Integer, default=0)
    config = Column(JSON)

    settings = relationship("Setting", back_populates="user", cascade="all, delete-orphan", uselist=False)
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quality = Column(Enum("high", "medium", "low", "audio", "custom"), nullable=False, default="high")
    format = Column(Enum("video", "audio", "document"), nullable=False, default="video")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="settings")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    method = Column(String(50), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(
        Enum(
            PaymentStatus.PENDING,
            PaymentStatus.COMPLETED,
            PaymentStatus.FAILED,
            PaymentStatus.REFUNDED,
        ),
        nullable=False,
    )
    transaction_id = Column(String(100))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="payments")


def create_session():
    engine = create_engine(
        os.getenv("DB_DSN"),
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


def get_quality_settings(tgid) -> Literal["high", "medium", "low", "audio", "custom"]:
    with session_manager() as session:
        user = session.query(User).filter(User.user_id == tgid).first()
        if user and user.settings:
            return user.settings.quality

        return "high"


def get_format_settings(tgid) -> Literal["video", "audio", "document"]:
    with session_manager() as session:
        user = session.query(User).filter(User.user_id == tgid).first()
        if user and user.settings:
            return user.settings.format
        return "video"


def set_user_settings(tgid: int, key: str, value: str):
    # set quality or format settings
    with session_manager() as session:
        # find user first
        user = session.query(User).filter(User.user_id == tgid).first()
        # upsert
        setting = session.query(Setting).filter(Setting.user_id == user.id).first()
        if setting:
            setattr(setting, key, value)
        else:
            session.add(Setting(user_id=user.id, **{key: value}))


def get_free_quota(uid: int):
    with session_manager() as session:
        data = session.query(User).filter(User.user_id == uid).first()
        if data:
            return data.free
        return FREE_DOWNLOAD


def get_paid_quota(uid: int):
    if os.getenv("ENABLE_VIP"):
        with session_manager() as session:
            data = session.query(User).filter(User.user_id == uid).first()
            if data:
                return data.paid

            return 0

    return math.inf


def reset_free_quota(uid: int):
    with session_manager() as session:
        data = session.query(User).filter(User.user_id == uid).first()
        if data:
            data.free = 5


def add_paid_quota(uid: int, amount: int):
    with session_manager() as session:
        data = session.query(User).filter(User.user_id == uid).first()
        if data:
            data.paid += amount


def use_quota(uid: int):
    # use free first, then paid
    with session_manager() as session:
        user = session.query(User).filter(User.user_id == uid).first()
        if user:
            if user.free > 0:
                user.free -= 1
            elif user.paid > 0:
                user.paid -= 1
            else:
                raise Exception("Quota exhausted")


def init_user(uid: int):
    with session_manager() as session:
        user = session.query(User).filter(User.user_id == uid).first()
        if not user:
            session.add(User(user_id=uid))


def reset_free():
    with session_manager() as session:
        users = session.query(User).all()
        for user in users:
            user.free = FREE_DOWNLOAD
        session.commit()


def credit_account(who, total_amount: int, quota: int, transaction, method="stripe"):
    with session_manager() as session:
        user = session.query(User).filter(User.user_id == who).first()
        if user:
            dollar = total_amount / 100
            user.paid += quota
            logging.info("user %d credited with %d tokens, payment:$%.2f", who, user.paid, dollar)
            session.add(
                Payment(
                    method=method,
                    amount=total_amount,
                    status=PaymentStatus.COMPLETED,
                    transaction_id=transaction,
                    user_id=user.id,
                )
            )
            session.commit()
            return user.free, user.paid

        return None, None
