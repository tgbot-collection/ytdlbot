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
import threading

from celery import Celery
from pyrogram import idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from client_init import create_app
from config import BROKER, ENABLE_CELERY, OWNER, WORKERS
from constant import BotText
from db import Redis
from downloader import convert_flac, sizeof_fmt, upload_hook, ytdl_download
from utils import (apply_log_formatter, customize_logger, get_metadata,
                   get_user_settings)

customize_logger(["pyrogram.client", "pyrogram.session.session", "pyrogram.connection.connection"])
apply_log_formatter()
bot_text = BotText()

# celery -A tasks worker --loglevel=info --pool=solo
# app = Celery('celery', broker=BROKER, accept_content=['pickle'], task_serializer='pickle')
app = Celery('tasks', broker=BROKER)

celery_client = create_app(":memory:")
celery_client.start()


@app.task()
def download_task(chat_id, message_id, url):
    logging.info("celery tasks started for %s", url)
    # print(celery_client.get_me())
    bot_msg = celery_client.get_messages(chat_id, message_id)
    normal_download(bot_msg, celery_client, url)
    logging.info("celery tasks ended.")


@app.task()
def audio_task(chat_id, message_id):
    logging.info("Audio celery tasks started for %s-%s", chat_id, message_id)
    bot_msg = celery_client.get_messages(chat_id, message_id)
    normal_audio(bot_msg)
    logging.info("Audio celery tasks ended.")


def download_entrance(bot_msg, client, url):
    if ENABLE_CELERY:
        download_task.delay(bot_msg.chat.id, bot_msg.message_id, url)
    else:
        normal_download(bot_msg, client, url)


def audio_entrance(bot_msg):
    if ENABLE_CELERY:
        audio_task.delay(bot_msg.chat.id, bot_msg.message_id)
    else:
        normal_audio(bot_msg)


def normal_audio(bot_msg):
    chat_id = bot_msg.chat.id
    mp4_name = bot_msg.video.file_name  # 'youtube-dl_test_video_a.mp4'
    flac_name = mp4_name.replace("mp4", "m4a")

    with tempfile.NamedTemporaryFile() as tmp:
        logging.info("downloading to %s", tmp.name)
        celery_client.send_chat_action(chat_id, 'record_video_note')
        celery_client.download_media(bot_msg, tmp.name)
        logging.info("downloading complete %s", tmp.name)
        # execute ffmpeg
        celery_client.send_chat_action(chat_id, 'record_audio')
        flac_tmp = convert_flac(flac_name, tmp)
        celery_client.send_chat_action(chat_id, 'upload_audio')
        celery_client.send_audio(chat_id, flac_tmp)
        Redis().update_metrics("audio_success")
        os.unlink(flac_tmp)


def get_worker_status(username):
    worker_name = os.getenv("WORKER_NAME")
    me = celery_client.get_me()
    if worker_name and username == OWNER:
        return f"Downloaded by {me.mention()}-{worker_name}"
    return f"Downloaded by {me.mention()}"


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
            worker = get_worker_status(bot_msg.chat.username)
            cap = f"`{filename}`\n\n{url}\n\nInfo: {meta['width']}x{meta['height']} {size}\n\n{remain}\n{worker}"
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


def run_celery():
    argv = [
        "-A", "tasks", 'worker', '--loglevel=info',
        "--pool=threads", f"--concurrency={WORKERS * 2}",
        "-n", f"{os.getenv('WORKER_NAME', '')}"
    ]
    app.worker_main(argv)


if __name__ == '__main__':
    threading.Thread(target=run_celery, daemon=True).start()
    idle()
    celery_client.stop()
