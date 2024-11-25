#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - config.py
# 8/28/21 15:01
#

__author__ = "Benny <benny.think@gmail.com>"

import os

# general settings
WORKERS: int = int(os.getenv("WORKERS", 100))
APP_ID: int = int(os.getenv("APP_ID"))
APP_HASH = os.getenv("APP_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER = os.getenv("OWNER")
# db settings
AUTHORIZED_USER: str = os.getenv("AUTHORIZED_USER", "")
MYSQL_DSN = os.getenv("MYSQL_DSN")
REDIS_HOST = os.getenv("REDIS_HOST")
ENABLE_FFMPEG = os.getenv("ENABLE_FFMPEG", False)
AUDIO_FORMAT = os.getenv("AUDIO_FORMAT")
ENABLE_ARIA2 = os.getenv("ENABLE_ARIA2", False)
RCLONE_PATH = os.getenv("RCLONE")

# payment settings
ENABLE_VIP = os.getenv("VIP", False)
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")
FREE_DOWNLOAD = os.getenv("FREE_DOWNLOAD", 5)
EXPIRE = 24 * 3600
TOKEN_PRICE = os.getenv("TOKEN_PRICE", 10)  # 1 USD=10 credits

# For advance users
# Please do not change, if you don't know what these are.
TG_NORMAL_MAX_SIZE = 2000 * 1024 * 1024
CAPTION_URL_LENGTH_LIMIT = 150

RATE_LIMIT = os.getenv("RATE_LIMIT", 120)
# This will set the value for the tmpfile path(engine path). If not, will return None and use system’s default path.
# Please ensure that the directory exists and you have necessary permissions to write to it.
TMPFILE_PATH = os.getenv("TMPFILE_PATH")
