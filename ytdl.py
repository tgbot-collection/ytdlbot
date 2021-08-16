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
import time
import typing

from pyrogram import Client, filters, types
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from tgbot_ping import get_runtime

from downloader import convert_flac, sizeof_fmt, upload_hook, ytdl_download
from limit import VIP

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(filename)s [%(levelname)s]: %(message)s')
api_id = int(os.getenv("APP_ID", 0))
api_hash = os.getenv("APP_HASH")
token = os.getenv("TOKEN")
app = Client("ytdl", api_id, api_hash, bot_token=token, workers=100)


@app.on_message(filters.command(["start"]))
def start_handler(client: "Client", message: "types.Message"):
    chat_id = message.chat.id
    used, total, ttl = VIP().check_remaining_quota(chat_id)
    refresh_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ttl + time.time()))
    caption = f"Remaining quota: {used} bytes({sizeof_fmt(used)})/ {total} bytes({sizeof_fmt(total)}), " \
              f"refresh at {refresh_time}\n"
    logging.info("Welcome to youtube-dl bot!")
    client.send_chat_action(chat_id, "typing")
    client.send_message(message.chat.id, "Wrapper for youtube-dl.\n\n" + caption)


@app.on_message(filters.command(["help"]))
def help_handler(client: "Client", message: "types.Message"):
    chat_id = message.chat.id
    client.send_chat_action(chat_id, "typing")
    client.send_message(chat_id, "Stop working? "
                                 "Wait a few seconds, send your link again or report bugs at "
                                 "https://github.com/tgbot-collection/ytdl-bot/issues")


@app.on_message(filters.command(["ping"]))
def ping_handler(client: "Client", message: "types.Message"):
    chat_id = message.chat.id
    client.send_chat_action(chat_id, "typing")
    bot_info = get_runtime("botsrunner_ytdl_1", "YouTube-dl")
    client.send_message(chat_id, bot_info)


@app.on_message(filters.command(["about"]))
def help_handler(client: "Client", message: "types.Message"):
    chat_id = message.chat.id
    client.send_chat_action(chat_id, "typing")
    client.send_message(chat_id, "YouTube-DL by @BennyThink\n"
                                 "GitHub: https://github.com/tgbot-collection/ytdl-bot")


@app.on_message()
def download_handler(client: "Client", message: "types.Message"):
    # check remaining quota
    chat_id = message.chat.id
    vip = VIP()
    used, _, ttl = vip.check_remaining_quota(chat_id)

    if used <= 0:
        refresh_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ttl + time.time()))
        logging.error("quota exceed for %s, try again in %s seconds(%s)", chat_id, ttl, refresh_time)
        message.reply_text(f"Quota exceed, try again in {ttl} seconds({refresh_time})", quote=True)
        return
    if message.chat.type != "private" and not message.text.lower().startswith("/ytdl"):
        logging.warning("%s, it's annoying me...🙄️ ", message.text)
        return

    url = re.sub(r'/ytdl\s*', '', message.text)
    logging.info("start %s", url)

    if not re.findall(r"^https?://", url.lower()):
        message.reply_text("I think you should send me a link.", quote=True)
        return

    bot_msg: typing.Union["types.Message", "typing.Any"] = message.reply_text("Processing", quote=True)
    client.send_chat_action(chat_id, 'upload_video')
    temp_dir = tempfile.TemporaryDirectory()

    result = ytdl_download(url, temp_dir.name, bot_msg)
    logging.info("Download complete.")

    markup = InlineKeyboardMarkup(
        [
            [  # First row
                InlineKeyboardButton(  # Generates a callback query when pressed
                    "audio",
                    callback_data="audio"
                )
            ]
        ]
    )

    if result["status"]:
        client.send_chat_action(chat_id, 'upload_document')
        video_path = result["filepath"]
        bot_msg.edit_text('Download complete. Sending now...')

        used, total, ttl = vip.check_remaining_quota(chat_id)
        refresh_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ttl + time.time()))
        caption = f"Remaining quota: {used} bytes({sizeof_fmt(used)})/{total} bytes({sizeof_fmt(total)}), " \
                  f"refresh at {refresh_time}\n\n{url}"
        client.send_video(chat_id, video_path, supports_streaming=True, caption=caption,
                          progress=upload_hook, progress_args=(bot_msg,), reply_markup=markup)
        bot_msg.edit_text('Download success!✅')
    else:
        client.send_chat_action(chat_id, 'typing')
        tb = result["error"][0:4000]
        bot_msg.edit_text(f"{url} download failed❌：\n```{tb}```")

    temp_dir.cleanup()


@app.on_callback_query()
def answer(client: "Client", callback_query: types.CallbackQuery):
    callback_query.answer(f"Converting to audio...please wait patiently")
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


if __name__ == '__main__':
    app.run()
