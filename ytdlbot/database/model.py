#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - model.py


from sqlalchemy import Column, Enum, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

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
    resolution = Column(String(50), nullable=False)
    method = Column(Enum("video", "document"), nullable=False)
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
    Session = sessionmaker(bind=engine)
    session = Session()
    return session


def get_user_settings():
    session = create_session()


def set_user_settings():
    pass


def update_free_usage():
    pass


def update_paid_usage():
    pass
