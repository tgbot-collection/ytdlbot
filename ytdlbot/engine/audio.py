#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - audio.py

import tempfile

from pyrogram import enums

from config import TMPFILE_PATH, Types
from helper import ytdl_download


def audio_download_entrance(url: str, client: Types.Client, bot_msg: Types.Message):
    chat_id = bot_msg.chat.id
    status_msg: Types.Message = bot_msg.reply_text("Downloading audio...", quote=True)
    with tempfile.TemporaryDirectory(prefix="ytdl-", dir=TMPFILE_PATH) as tmp:
        client.send_chat_action(chat_id, enums.ChatAction.RECORD_AUDIO)
        filepath = ytdl_download(url, tmp, status_msg)
        status_msg.edit_text("Sending audio now...")
        client.send_chat_action(chat_id, enums.ChatAction.UPLOAD_AUDIO)
        for f in filepath:
            client.send_audio(chat_id, f)
        status_msg.edit_text("✅complete.")


def audio_convert_entrance():
    pass
