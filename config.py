#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - config.py
# 8/28/21 15:01
#

__author__ = "Benny <benny.think@gmail.com>"

import os

QUOTA = os.getenv("QUOTA", 5 * 1024 * 1024 * 1024)  # 5G
if os.uname().sysname == "Darwin":
    QUOTA = 10 * 1024 * 1024  # 10M

EX = os.getenv("EX", 24 * 3600)
MULTIPLY = os.getenv("MULTIPLY", 5)  # VIP1 is 5*5-25G, VIP2 is 50G
USD2CNY = os.getenv("USD2CNY", 6)  # $5 --> ¥30

ENABLE_VIP = os.getenv("VIP", False)
AFD_LINK = os.getenv("AFD_LINK", "https://afdian.net/@BennyThink")
COFFEE_LINK = os.getenv("COFFEE_LINK", "https://www.buymeacoffee.com/bennythink")
COFFEE_TOKEN = os.getenv("COFFEE_TOKEN")
AFD_TOKEN = os.getenv("AFD_TOKEN")
AFD_USER_ID = os.getenv("AFD_USER_ID")

OWNER = os.getenv("OWNER", "BennyThink")

APP_ID: "int" = int(os.getenv("APP_ID", 111))
APP_HASH = os.getenv("APP_HASH", "111")
TOKEN = os.getenv("TOKEN", "3703WLI")
REDIS = os.getenv("REDIS")
AUTHORIZED_USER: "str" = os.getenv("AUTHORIZED", "")

WORKERS: "int" = int(os.getenv("WORKERS", 300))
