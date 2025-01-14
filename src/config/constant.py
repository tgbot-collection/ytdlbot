#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - constant.py
# 8/16/21 16:59
#

__author__ = "Benny <benny.think@gmail.com>"

import typing

from pyrogram import Client, types


class BotText:

    start = """
    Welcome to YouTube Download bot. Type /help for more information.
    EU🇪🇺: @benny_2ytdlbot
    SG🇸🇬：@benny_ytdlbot

    Join https://t.me/+OGRC8tp9-U9mZDZl for updates.\n\n"""

    help = """
1. For YouTube and any websites supported by yt-dlp, just send the link and we will engine and send it to you.

2. For specific links use `/spdl {URL}`. More info at https://github.com/SanujaNS/ytdlbot-telegram#supported-websites 

3. If the bot doesn't work, try again or join https://t.me/+OGRC8tp9-U9mZDZl for updates.

4. Want to deploy it yourself?\nHere's the source code: https://github.com/tgbot-collection/ytdlbot
    """

    about = "YouTube Downloader by @BennyThink.\n\nOpen source on GitHub: https://github.com/tgbot-collection/ytdlbot"

    settings = """
Please choose the preferred format and video quality for your video. These settings only **apply to YouTube videos**.
High: 1080P
Medium: 720P
Low: 480P

If you choose to send the video as a document, Telegram client will not be able stream it.

Your current settings:
Video quality: {}
Sending type: {}
"""


class Types:
    Message = typing.Union[types.Message, typing.Coroutine]
    Client = Client
