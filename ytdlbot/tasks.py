#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - tasks.py
# 12/29/21 14:57
#

__author__ = "Benny <benny.think@gmail.com>"

import logging
import os
import pathlib
import tempfile

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from constant import BotText
from db import Redis
from downloader import sizeof_fmt, upload_hook, ytdl_download
from utils import get_metadata, get_user_settings

bot_text = BotText()

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(filename)s [%(levelname)s]: %(message)s')


def normal_download(bot_msg, client, url):
    chat_id = bot_msg.chat.id
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
        video_paths = result["filepath"]
        bot_msg.edit_text('Download complete. Sending now...')
        for video_path in video_paths:
            filename = pathlib.Path(video_path).name
            remain = bot_text.remaining_quota_caption(chat_id)
            size = sizeof_fmt(os.stat(video_path).st_size)
            meta = get_metadata(video_path)
            cap = f"`{filename}`\n\n{url}\n\nInfo: {meta['width']}x{meta['height']} {size}\n\n{remain}"
            settings = get_user_settings(str(chat_id))
            if settings[2] == "document":
                logging.info("Sending as document")
                client.send_document(chat_id, video_path,
                                     caption=cap,
                                     progress=upload_hook, progress_args=(bot_msg,),
                                     reply_markup=markup,
                                     thumb=meta["thumb"]
                                     )
            else:
                logging.info("Sending as video")
                client.send_video(chat_id, video_path,
                                  supports_streaming=True,
                                  caption=cap,
                                  progress=upload_hook, progress_args=(bot_msg,),
                                  reply_markup=markup,
                                  **meta
                                  )
            Redis().update_metrics("video_success")
        bot_msg.edit_text('Download success!✅')
    else:
        client.send_chat_action(chat_id, 'typing')
        tb = result["error"][0:4000]
        bot_msg.edit_text(f"Download failed!❌\n\n```{tb}```", disable_web_page_preview=True)

    temp_dir.cleanup()

