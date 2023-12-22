#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - config.py
# 8/28/21 15:01
#

__author__ = "Benny <benny.think@gmail.com>"

import os

from blinker import signal

# general settings
WORKERS: int = int(os.getenv("WORKERS", 10))
PYRO_WORKERS: int = int(os.getenv("PYRO_WORKERS", 100))
APP_ID: int = int(os.getenv("APP_ID", 198214))
APP_HASH = os.getenv("APP_HASH", "1234b90")
TOKEN = os.getenv("TOKEN", "1234")

REDIS = os.getenv("REDIS", "redis")

TG_PREMIUM_MAX_SIZE = 4000 * 1024 * 1024
TG_NORMAL_MAX_SIZE = 2000 * 1024 * 1024
# TG_NORMAL_MAX_SIZE = 10 * 1024 * 1024


EXPIRE = 24 * 3600

ENABLE_VIP = os.getenv("VIP", False)
OWNER = os.getenv("OWNER", "BennyThink")

# limitation settings
AUTHORIZED_USER: str = os.getenv("AUTHORIZED_USER", "")
# membership requires: the format could be username(without @ sign)/chat_id of channel or group.
# You need to add the bot to this group/channel as admin
REQUIRED_MEMBERSHIP: str = os.getenv("REQUIRED_MEMBERSHIP", "")

# celery related
IS_BACKUP_BOT = os.getenv("IS_BACKUP_BOT")
ENABLE_CELERY = os.getenv("ENABLE_CELERY", False)
if IS_BACKUP_BOT:
    BROKER = os.getenv("BROKER", f"redis://{REDIS}:6379/1")
else:
    BROKER = os.getenv("BROKER", f"redis://{REDIS}:6379/0")

MYSQL_HOST = os.getenv("MYSQL_HOST", "mysql")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASS = os.getenv("MYSQL_PASS", "root")

AUDIO_FORMAT = os.getenv("AUDIO_FORMAT")
ARCHIVE_ID = os.getenv("ARCHIVE_ID")

IPv6 = os.getenv("IPv6", False)
ENABLE_FFMPEG = os.getenv("ENABLE_FFMPEG", False)

PLAYLIST_SUPPORT = os.getenv("PLAYLIST_SUPPORT", False)
M3U8_SUPPORT = os.getenv("M3U8_SUPPORT", False)
ENABLE_ARIA2 = os.getenv("ENABLE_ARIA2", False)

RATE_LIMIT = os.getenv("RATE_LIMIT", 120)
RCLONE_PATH = os.getenv("RCLONE")
# This will set the value for the tmpfile path(download path) if it is set.
# If TMPFILE is not set, it will return None and use system’s default temporary file path.
# Please ensure that the directory exists and you have necessary permissions to write to it.
# If you don't know what this is just leave it as it is.
TMPFILE_PATH = os.getenv("TMPFILE")

# payment settings
AFD_LINK = os.getenv("AFD_LINK", "https://afdian.net/@BennyThink")
COFFEE_LINK = os.getenv("COFFEE_LINK", "https://www.buymeacoffee.com/bennythink")
COFFEE_TOKEN = os.getenv("COFFEE_TOKEN")
AFD_TOKEN = os.getenv("AFD_TOKEN")
AFD_USER_ID = os.getenv("AFD_USER_ID")
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN") or "1234"
FREE_DOWNLOAD = os.getenv("FREE_DOWNLOAD", 10)
TOKEN_PRICE = os.getenv("BUY_UNIT", 20)  # one USD=20 credits
TRONGRID_KEY = os.getenv("TRONGRID_KEY", "").split(",")
# the default mnemonic is for nile testnet
TRON_MNEMONIC = os.getenv("TRON_MNEMONIC", "cram floor today legend service drill pitch leaf car govern harvest soda")
TRX_SIGNAL = signal("trx_received")

PREMIUM_USER = int(os.getenv("PREMIUM_USER", "0"))


class FileTooBig(Exception):
    pass
