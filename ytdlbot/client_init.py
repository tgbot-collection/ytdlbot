#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - client_init.py
# 12/29/21 16:20
#

__author__ = "Benny <benny.think@gmail.com>"

from pyrogram import Client

from config import APP_HASH, APP_ID, TOKEN


def create_app(session="ytdl", workers=100):
    _app = Client(session, APP_ID, APP_HASH,
                  bot_token=TOKEN, workers=workers,
                  # proxy={"hostname": "host.docker.internal", "port": 1080}
                  )

    return _app
