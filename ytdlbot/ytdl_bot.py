#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - new.py
# 8/14/21 14:37
#

__author__ = "Benny <benny.think@gmail.com>"

import logging
import os
import re
import tempfile
import typing

from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client, filters, types
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from tgbot_ping import get_runtime

from client_init import create_app
from config import (AUTHORIZED_USER, ENABLE_CELERY, ENABLE_VIP, OWNER,
                    REQUIRED_MEMBERSHIP)
from constant import BotText
from db import MySQL, Redis
from downloader import convert_flac
from limit import verify_payment
from tasks import download_entrance
from utils import customize_logger, get_user_settings, set_user_settings, get_revision_tag

customize_logger(["pyrogram.client", "pyrogram.session.session", "pyrogram.connection.connection"])
app = create_app()
bot_text = BotText()

logging.info("Authorized users are %s", AUTHORIZED_USER)


def private_use(func):
    def wrapper(client: "Client", message: "types.Message"):
        chat_id = getattr(message.from_user, "id", None)

        # message type check
        if message.chat.type != "private" and not message.text.lower().startswith("/ytdl"):
            logging.warning("%s, it's annoying me...🙄️ ", message.text)
            return

        # authorized users check
        if AUTHORIZED_USER:
            users = [int(i) for i in AUTHORIZED_USER.split(",")]
        else:
            users = []

        if users and chat_id and chat_id not in users:
            message.reply_text(bot_text.private, quote=True)
            return

        # membership check
        if REQUIRED_MEMBERSHIP:
            try:
                app.get_chat_member(REQUIRED_MEMBERSHIP, chat_id)
                logging.info("user %s check passed for group/channel %s.", chat_id, REQUIRED_MEMBERSHIP)
            except UserNotParticipant:
                logging.warning("user %s is not a member of group/channel %s", chat_id, REQUIRED_MEMBERSHIP)
                message.reply_text(bot_text.membership_require, quote=True)
                return

        return func(client, message)

    return wrapper


@app.on_message(filters.command(["start"]))
def start_handler(client: "Client", message: "types.Message"):
    chat_id = message.chat.id
    logging.info("Welcome to youtube-dl bot!")
    client.send_chat_action(chat_id, "typing")
    greeting = bot_text.get_vip_greeting(chat_id)
    client.send_message(message.chat.id, greeting + bot_text.start + "\n\n" + bot_text.remaining_quota_caption(chat_id))


@app.on_message(filters.command(["help"]))
def help_handler(client: "Client", message: "types.Message"):
    chat_id = message.chat.id
    client.send_chat_action(chat_id, "typing")
    client.send_message(chat_id, bot_text.help, disable_web_page_preview=True)


@app.on_message(filters.command(["ping"]))
def ping_handler(client: "Client", message: "types.Message"):
    chat_id = message.chat.id
    client.send_chat_action(chat_id, "typing")
    if os.uname().sysname == "Darwin" or ".heroku" in os.getenv("PYTHONHOME", ""):
        bot_info = "ping unavailable."
    else:
        bot_info = get_runtime("ytdlbot_ytdl_1", "YouTube-dl")
    if message.chat.username == OWNER:
        client.send_document(chat_id, Redis().generate_file(), caption=bot_info)
    else:
        client.send_message(chat_id, f"{bot_info}")


@app.on_message(filters.command(["about"]))
def help_handler(client: "Client", message: "types.Message"):
    chat_id = message.chat.id
    client.send_chat_action(chat_id, "typing")
    client.send_message(chat_id, bot_text.about)


@app.on_message(filters.command(["terms"]))
def terms_handler(client: "Client", message: "types.Message"):
    chat_id = message.chat.id
    client.send_chat_action(chat_id, "typing")
    client.send_message(chat_id, bot_text.terms)


@app.on_message(filters.command(["settings"]))
def settings_handler(client: "Client", message: "types.Message"):
    chat_id = message.chat.id
    client.send_chat_action(chat_id, "typing")
    markup = InlineKeyboardMarkup(
        [
            [  # First row
                InlineKeyboardButton("send as document", callback_data="document"),
                InlineKeyboardButton("send as video", callback_data="video")
            ],
            [  # second row
                InlineKeyboardButton("High Quality", callback_data="high"),
                InlineKeyboardButton("Medium Quality", callback_data="medium"),
                InlineKeyboardButton("Low Quality", callback_data="low"),
            ],
        ]
    )

    data = get_user_settings(str(chat_id))
    client.send_message(chat_id, bot_text.settings.format(data[1], data[2]), reply_markup=markup)


@app.on_message(filters.command(["vip"]))
def vip_handler(client: "Client", message: "types.Message"):
    chat_id = message.chat.id
    text = message.text.strip()
    client.send_chat_action(chat_id, "typing")
    if text == "/vip":
        client.send_message(chat_id, bot_text.vip, disable_web_page_preview=True)
    else:
        bm: typing.Union["types.Message", "typing.Any"] = message.reply_text(bot_text.vip_pay, quote=True)
        unique = text.replace("/vip", "").strip()
        msg = verify_payment(chat_id, unique)
        bm.edit_text(msg)


@app.on_message(filters.incoming)
@private_use
def download_handler(client: "Client", message: "types.Message"):
    # check remaining quota
    chat_id = message.chat.id
    Redis().user_count(chat_id)

    url = re.sub(r'/ytdl\s*', '', message.text)
    logging.info("start %s", url)

    if not re.findall(r"^https?://", url.lower()):
        Redis().update_metrics("bad_request")
        message.reply_text("I think you should send me a link.", quote=True)
        return

    Redis().update_metrics("video_request")
    bot_msg: typing.Union["types.Message", "typing.Any"] = message.reply_text("Processing", quote=True)
    client.send_chat_action(chat_id, 'upload_video')
    # temp_dir = tempfile.TemporaryDirectory()
    download_entrance(bot_msg, client, url)

    # temp_dir.cleanup()


@app.on_callback_query(filters.regex(r"document|video"))
def send_method_callback(client: "Client", callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    data = callback_query.data
    logging.info("Setting %s file type to %s", chat_id, data)
    set_user_settings(chat_id, "method", data)
    callback_query.answer(f"Your video send type was set to {callback_query.data}")


@app.on_callback_query(filters.regex(r"high|medium|low"))
def download_resolution_callback(client: "Client", callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    data = callback_query.data
    logging.info("Setting %s file type to %s", chat_id, data)
    set_user_settings(chat_id, "resolution", data)
    callback_query.answer(f"Your default download quality was set to {callback_query.data}")


@app.on_callback_query(filters.regex(r"audio"))
def audio_callback(client: "Client", callback_query: types.CallbackQuery):
    callback_query.answer(f"Converting to audio...please wait patiently")
    Redis().update_metrics("audio_request")

    msg = callback_query.message

    chat_id = msg.chat.id
    mp4_name = msg.video.file_name  # 'youtube-dl_test_video_a.mp4'
    flac_name = mp4_name.replace("mp4", "m4a")

    with tempfile.NamedTemporaryFile() as tmp:
        logging.info("downloading to %s", tmp.name)
        client.send_chat_action(chat_id, 'record_video_note')
        client.download_media(msg, tmp.name)
        logging.info("downloading complete %s", tmp.name)
        # execute ffmpeg
        client.send_chat_action(chat_id, 'record_audio')
        flac_tmp = convert_flac(flac_name, tmp)
        client.send_chat_action(chat_id, 'upload_audio')
        client.send_audio(chat_id, flac_tmp)
        Redis().update_metrics("audio_success")
        os.unlink(flac_tmp)


if __name__ == '__main__':
    MySQL()
    revision_tag = get_revision_tag()
    scheduler = BackgroundScheduler()
    scheduler.add_job(Redis().reset_today, 'cron', hour=0, minute=0)
    scheduler.start()
    banner = f"""
▌ ▌         ▀▛▘     ▌       ▛▀▖              ▜            ▌
▝▞  ▞▀▖ ▌ ▌  ▌  ▌ ▌ ▛▀▖ ▞▀▖ ▌ ▌ ▞▀▖ ▌  ▌ ▛▀▖ ▐  ▞▀▖ ▝▀▖ ▞▀▌
 ▌  ▌ ▌ ▌ ▌  ▌  ▌ ▌ ▌ ▌ ▛▀  ▌ ▌ ▌ ▌ ▐▐▐  ▌ ▌ ▐  ▌ ▌ ▞▀▌ ▌ ▌
 ▘  ▝▀  ▝▀▘  ▘  ▝▀▘ ▀▀  ▝▀▘ ▀▀  ▝▀   ▘▘  ▘ ▘  ▘ ▝▀  ▝▀▘ ▝▀▘

By @BennyThink, VIP mode: {ENABLE_VIP}, Distribution: {ENABLE_CELERY}
Version: {revision_tag[0]}@{revision_tag[1]}
    """
    print(banner)
    app.run()
