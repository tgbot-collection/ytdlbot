#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - tasks.py
# 12/29/21 14:57
#

__author__ = "Benny <benny.think@gmail.com>"

import logging
import os
import pathlib
import re
import subprocess
import tempfile
import threading
import time
import traceback
import typing
from hashlib import md5
from urllib.parse import quote_plus

import psutil
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from celery import Celery
from celery.worker.control import Panel
from pyrogram import Client, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

from client_init import create_app
from config import (ARCHIVE_ID, AUDIO_FORMAT, BROKER, ENABLE_CELERY,
                    ENABLE_VIP, TG_MAX_SIZE, WORKERS)
from constant import BotText
from db import Redis
from downloader import (edit_text, run_ffmpeg, sizeof_fmt, tqdm_progress,
                        upload_hook, ytdl_download)
from limit import VIP
from utils import (apply_log_formatter, auto_restart, customize_logger,
                   get_metadata, get_revision, get_user_settings)

customize_logger(["pyrogram.client", "pyrogram.session.session", "pyrogram.connection.connection"])
apply_log_formatter()
bot_text = BotText()
logging.getLogger('apscheduler.executors.default').propagate = False

# celery -A tasks worker --loglevel=info --pool=solo
# app = Celery('celery', broker=BROKER, accept_content=['pickle'], task_serializer='pickle')
app = Celery('tasks', broker=BROKER)

celery_client = create_app(":memory:")


def get_messages(chat_id, message_id):
    try:
        return celery_client.get_messages(chat_id, message_id)
    except ConnectionError as e:
        logging.critical("WTH!!! %s", e)
        celery_client.start()
        return celery_client.get_messages(chat_id, message_id)


@app.task()
def ytdl_download_task(chat_id, message_id, url):
    logging.info("YouTube celery tasks started for %s", url)
    bot_msg = get_messages(chat_id, message_id)
    ytdl_normal_download(bot_msg, celery_client, url)
    logging.info("YouTube celery tasks ended.")


@app.task()
def audio_task(chat_id, message_id):
    logging.info("Audio celery tasks started for %s-%s", chat_id, message_id)
    bot_msg = get_messages(chat_id, message_id)
    normal_audio(bot_msg, celery_client)
    logging.info("Audio celery tasks ended.")


def get_unique_clink(original_url, user_id):
    settings = get_user_settings(str(user_id))
    clink = VIP().extract_canonical_link(original_url)
    try:
        unique = "{}?p={}{}".format(clink, *settings[1:])
    except IndexError:
        unique = clink
    return unique


@app.task()
def direct_download_task(chat_id, message_id, url):
    logging.info("Direct download celery tasks started for %s", url)
    bot_msg = get_messages(chat_id, message_id)
    direct_normal_download(bot_msg, celery_client, url)
    logging.info("Direct download celery tasks ended.")


def forward_video(url, client, bot_msg):
    chat_id = bot_msg.chat.id
    red = Redis()
    vip = VIP()
    unique = get_unique_clink(url, chat_id)

    cached_fid = red.get_send_cache(unique)
    if not cached_fid:
        return False

    try:
        res_msg: "Message" = upload_processor(client, bot_msg, url, cached_fid)
        if not res_msg:
            raise ValueError("Failed to forward message")
        obj = res_msg.document or res_msg.video or res_msg.audio
        if ENABLE_VIP:
            file_size = getattr(obj, "file_size", None) \
                        or getattr(obj, "file_size", None) \
                        or getattr(obj, "file_size", 10)
            # TODO: forward file size may exceed the limit
            vip.use_quota(chat_id, file_size)
        caption, _ = gen_cap(bot_msg, url, obj)
        res_msg.edit_text(caption, reply_markup=gen_video_markup())
        bot_msg.edit_text(f"Download success!✅✅✅")
        red.update_metrics("cache_hit")
        return True

    except Exception as e:
        traceback.print_exc()
        logging.error("Failed to forward message %s", e)
        red.del_send_cache(unique)
        red.update_metrics("cache_miss")


def ytdl_download_entrance(bot_msg, client, url):
    chat_id = bot_msg.chat.id
    if forward_video(url, client, bot_msg):
        return
    mode = get_user_settings(str(chat_id))[-1]
    if ENABLE_CELERY and mode in [None, "Celery"]:
        ytdl_download_task.delay(chat_id, bot_msg.message_id, url)
    else:
        ytdl_normal_download(bot_msg, client, url)


def direct_download_entrance(bot_msg, client, url):
    if ENABLE_CELERY:
        # TODO disable it for now
        direct_normal_download(bot_msg, client, url)
        # direct_download_task.delay(bot_msg.chat.id, bot_msg.message_id, url)
    else:
        direct_normal_download(bot_msg, client, url)


def audio_entrance(bot_msg, client):
    if ENABLE_CELERY:
        audio_task.delay(bot_msg.chat.id, bot_msg.message_id)
    else:
        normal_audio(bot_msg, client)


def direct_normal_download(bot_msg, client, url):
    chat_id = bot_msg.chat.id
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36"}
    vip = VIP()
    length = 0
    if ENABLE_VIP:
        remain, _, _ = vip.check_remaining_quota(chat_id)
        try:
            head_req = requests.head(url, headers=headers)
            length = int(head_req.headers.get("content-length"))
        except (TypeError, requests.exceptions.RequestException):
            length = 0
        if remain < length:
            bot_msg.reply_text(f"Sorry, you have reached your quota.\n")
            return

    req = None
    try:
        req = requests.get(url, headers=headers, stream=True)
        length = int(req.headers.get("content-length"))
        filename = re.findall("filename=(.+)", req.headers.get("content-disposition"))[0]
    except TypeError:
        filename = getattr(req, "url", "").rsplit("/")[-1]
    except Exception as e:
        bot_msg.edit_text(f"Download failed!❌\n\n```{e}```", disable_web_page_preview=True)
        return

    if not filename:
        filename = quote_plus(url)

    with tempfile.TemporaryDirectory(prefix="ytdl-") as f:
        filepath = f"{f}/{filename}"
        # consume the req.content
        downloaded = 0
        for chunk in req.iter_content(1024 * 1024):
            text = tqdm_progress("Downloading...", length, downloaded)
            edit_text(bot_msg, text)
            with open(filepath, "ab") as fp:
                fp.write(chunk)
            downloaded += len(chunk)
        logging.info("Downloaded file %s", filename)
        st_size = os.stat(filepath).st_size
        if ENABLE_VIP:
            vip.use_quota(chat_id, st_size)
        client.send_chat_action(chat_id, "upload_document")
        client.send_document(bot_msg.chat.id, filepath,
                             caption=f"filesize: {sizeof_fmt(st_size)}",
                             progress=upload_hook, progress_args=(bot_msg,),
                             )
        bot_msg.edit_text("Download success!✅")


def normal_audio(bot_msg, client):
    chat_id = bot_msg.chat.id
    # fn = getattr(bot_msg.video, "file_name", None) or getattr(bot_msg.document, "file_name", None)
    status_msg = bot_msg.reply_text("Converting to audio...please wait patiently", quote=True)
    orig_url: "str" = re.findall(r"http[s]://.*", bot_msg.caption)[0]
    with tempfile.TemporaryDirectory(prefix="ytdl-") as tmp:
        client.send_chat_action(chat_id, 'record_audio')
        # just try to download the audio using yt-dlp
        resp = ytdl_download(orig_url, tmp, status_msg, hijack="bestaudio[ext=m4a]")
        status_msg.edit_text("Sending audio now...")
        client.send_chat_action(chat_id, 'upload_audio')
        for f in resp["filepath"]:
            client.send_audio(chat_id, f)
        status_msg.edit_text("✅ Conversion complete.")
        Redis().update_metrics("audio_success")


def get_dl_source():
    worker_name = os.getenv("WORKER_NAME")
    if worker_name:
        return f"Downloaded by  {worker_name}"
    return ""


def upload_transfer_sh(bm, paths: list) -> "str":
    d = {p.name: (md5(p.name.encode("utf8")).hexdigest() + p.suffix, p.open("rb")) for p in paths}
    monitor = MultipartEncoderMonitor(MultipartEncoder(fields=d), lambda x: upload_hook(x.bytes_read, x.len, bm))
    headers = {'Content-Type': monitor.content_type}
    try:
        req = requests.post("https://transfer.sh", data=monitor, headers=headers)
        bm.edit_text(f"Download success!✅")
        return re.sub(r"https://", "\nhttps://", req.text)
    except requests.exceptions.RequestException as e:
        return f"Upload failed!❌\n\n```{e}```"


def ytdl_normal_download(bot_msg, client, url):
    chat_id = bot_msg.chat.id
    temp_dir = tempfile.TemporaryDirectory(prefix="ytdl-")

    result = ytdl_download(url, temp_dir.name, bot_msg)
    logging.info("Download complete.")
    if result["status"]:
        client.send_chat_action(chat_id, 'upload_document')
        video_paths = result["filepath"]
        bot_msg.edit_text('Download complete. Sending now...')
        for video_path in video_paths:
            # normally there's only one video in that path...
            st_size = os.stat(video_path).st_size
            if st_size > TG_MAX_SIZE:
                t = f"Your video({sizeof_fmt(st_size)}) is too large for Telegram. I'll upload it to transfer.sh"
                bot_msg.edit_text(t)
                client.send_chat_action(chat_id, 'upload_document')
                client.send_message(chat_id, upload_transfer_sh(bot_msg, video_paths))
                return
            upload_processor(client, bot_msg, url, video_path)
        bot_msg.edit_text('Download success!✅')
    else:
        client.send_chat_action(chat_id, 'typing')
        tb = result["error"][0:4000]
        bot_msg.edit_text(f"Download failed!❌\n\n```{tb}```", disable_web_page_preview=True)

    temp_dir.cleanup()


def upload_processor(client, bot_msg, url, vp_or_fid: "typing.Any[str, pathlib.Path]"):
    chat_id = bot_msg.chat.id
    red = Redis()
    markup = gen_video_markup()
    cap, meta = gen_cap(bot_msg, url, vp_or_fid)
    settings = get_user_settings(str(chat_id))
    if ARCHIVE_ID and isinstance(vp_or_fid, pathlib.Path):
        chat_id = ARCHIVE_ID
    if settings[2] == "document":
        logging.info("Sending as document")
        res_msg = client.send_document(chat_id, vp_or_fid,
                                       caption=cap,
                                       progress=upload_hook, progress_args=(bot_msg,),
                                       reply_markup=markup,
                                       thumb=meta["thumb"]
                                       )
    elif settings[2] == "audio":
        logging.info("Sending as audio")
        res_msg = client.send_audio(chat_id, vp_or_fid,
                                    caption=cap,
                                    progress=upload_hook, progress_args=(bot_msg,),
                                    )
    else:
        logging.info("Sending as video")
        res_msg = client.send_video(chat_id, vp_or_fid,
                                    supports_streaming=True,
                                    caption=cap,
                                    progress=upload_hook, progress_args=(bot_msg,),
                                    reply_markup=markup,
                                    **meta
                                    )
    unique = get_unique_clink(url, bot_msg.chat.id)
    obj = res_msg.document or res_msg.video or res_msg.audio
    red.add_send_cache(unique, getattr(obj, "file_id", None))
    red.update_metrics("video_success")
    if ARCHIVE_ID and isinstance(vp_or_fid, pathlib.Path):
        client.forward_messages(bot_msg.chat.id, ARCHIVE_ID, res_msg.message_id)
    return res_msg


def gen_cap(bm, url, video_path):
    chat_id = bm.chat.id
    user = bm.chat
    try:
        user_info = "@{}({})-{}".format(
            user.username or "N/A",
            user.first_name or "" + user.last_name or "",
            user.id
        )
    except Exception:
        user_info = ""

    if isinstance(video_path, pathlib.Path):
        meta = get_metadata(video_path)
        file_name = video_path.name
        file_size = sizeof_fmt(os.stat(video_path).st_size)
    else:
        file_name = getattr(video_path, "file_name", "")
        file_size = sizeof_fmt(getattr(video_path, "file_size", (2 << 6) - (2 << 4) - (2 << 2) + (0 ^ 1) + (2 << 5)))
        meta = dict(
            width=getattr(video_path, "width", 0),
            height=getattr(video_path, "height", 0),
            duration=getattr(video_path, "duration", 0),
            thumb=getattr(video_path, "thumb", None),
        )
    remain = bot_text.remaining_quota_caption(chat_id)
    worker = get_dl_source()
    cap = f"{user_info}\n`{file_name}`\n\n{url}\n\nInfo: {meta['width']}x{meta['height']} {file_size}\t" \
          f"{meta['duration']}s\n{remain}\n{worker}\n{bot_text.custom_text}"
    return cap, meta


def gen_video_markup():
    markup = InlineKeyboardMarkup(
        [
            [  # First row
                InlineKeyboardButton(  # Generates a callback query when pressed
                    "convert to audio",
                    callback_data="convert"
                )
            ]
        ]
    )
    return markup


@Panel.register
def ping_revision(*args):
    return get_revision()


@Panel.register
def hot_patch(*args):
    app_path = pathlib.Path().cwd().parent
    logging.info("Hot patching on path %s...", app_path)

    apk_install = "xargs apk add  < apk.txt"
    pip_install = "pip install -r requirements.txt"
    unset = "git config --unset http.https://github.com/.extraheader"
    pull_unshallow = "git pull origin --unshallow"
    pull = "git pull"

    subprocess.call(unset, shell=True, cwd=app_path)
    if subprocess.call(pull_unshallow, shell=True, cwd=app_path) != 0:
        logging.info("Already unshallow, pulling now...")
        subprocess.call(pull, shell=True, cwd=app_path)

    logging.info("Code is updated, applying hot patch now...")
    subprocess.call(apk_install, shell=True, cwd=app_path)
    subprocess.call(pip_install, shell=True, cwd=app_path)
    psutil.Process().kill()


def run_celery():
    argv = [
        "-A", "tasks", 'worker', '--loglevel=info',
        "--pool=threads", f"--concurrency={WORKERS}",
        "-n", os.getenv("WORKER_NAME", "")
    ]
    app.worker_main(argv)


if __name__ == '__main__':
    celery_client.start()
    print("Bootstrapping Celery worker now.....")
    time.sleep(5)
    threading.Thread(target=run_celery, daemon=True).start()

    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(auto_restart, 'interval', seconds=5)
    scheduler.start()

    idle()
    celery_client.stop()
