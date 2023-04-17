#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - client_init.py
# 12/29/21 16:20
#

__author__ = "Benny <benny.think@gmail.com>"

from pyrogram import Client

from config import APP_HASH, APP_ID, PYRO_WORKERS, TOKEN, IPv6


def create_app(session: str, workers: int = PYRO_WORKERS) -> Client:
    _app = Client(
        session,
        APP_ID,
        APP_HASH,
        bot_token=TOKEN,
        workers=workers,
        ipv6=IPv6,
    )

    return _app
