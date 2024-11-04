#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - client_init.py
# 12/29/21 16:20
#

__author__ = "Benny <benny.think@gmail.com>"

from pyrogram import Client

from config import APP_HASH, APP_ID, TOKEN


def create_app(name: str, workers: int = 32) -> Client:
    return Client(
        name,
        APP_ID,
        APP_HASH,
        bot_token=TOKEN,
        workers=workers,
        # max_concurrent_transmissions=max(1, WORKERS // 2),
        # https://github.com/pyrogram/pyrogram/issues/1225#issuecomment-1446595489
    )
