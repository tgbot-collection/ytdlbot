#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - tasks.py
# 12/29/21 14:57
#

__author__ = "Benny <benny.think@gmail.com>"

import logging
import math
import os
import pathlib
import random
import re
import subprocess
import tempfile
import threading
import time
import traceback
import typing
from hashlib import md5
from urllib.parse import quote_plus

import filetype
import psutil
import pyrogram.errors
import requests
import sentry_sdk
from apscheduler.schedulers.background import BackgroundScheduler
from celery import Celery
from celery.worker.control import Panel
from pyrogram import Client, idle, types
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
from sentry_sdk.integrations.celery import CeleryIntegration

from channel import Channel
from client_init import create_app
from config import (
    ARCHIVE_ID,
    BROKER,
    DSN,
    ENABLE_CELERY,
    ENABLE_QUEUE,
    ENABLE_VIP,
    OWNER,
    RATE_LIMIT,
    WORKERS,
)
from constant import BotText
from database import Redis
from downloader import edit_text, tqdm_progress, upload_hook, ytdl_download
from limit import Payment
from utils import (
    apply_log_formatter,
    auto_restart,
    customize_logger,
    get_metadata,
    get_revision,
    sizeof_fmt,
)

customize_logger(["pyrogram.client", "pyrogram.session.session", "pyrogram.connection.connection"])
apply_log_formatter()
bot_text = BotText()
logging.getLogger("apscheduler.executors.default").propagate = False

# celery -A tasks worker --loglevel=info --pool=solo
# app = Celery('celery', broker=BROKER, accept_content=['pickle'], task_serializer='pickle')
app = Celery("tasks", broker=BROKER)
redis = Redis()
channel = Channel()

session = "ytdl-celery"
celery_client = create_app(session)
if DSN:
    sentry_sdk.init(DSN, integrations=[CeleryIntegration()])


def get_messages(chat_id, message_id):
    try:
        return celery_client.get_messages(chat_id, message_id)
    except ConnectionError as e:
        logging.critical("WTH!!! %s", e)
        celery_client.start()
        return celery_client.get_messages(chat_id, message_id)


@app.task(rate_limit=f"{RATE_LIMIT}/m")
def ytdl_download_task(chat_id, message_id, url: str):
    logging.info("YouTube celery tasks started for %s", url)
    bot_msg = get_messages(chat_id, message_id)
    ytdl_normal_download(celery_client, bot_msg, url)
    logging.info("YouTube celery tasks ended.")


@app.task()
def audio_task(chat_id, message_id):
    logging.info("Audio celery tasks started for %s-%s", chat_id, message_id)
    bot_msg = get_messages(chat_id, message_id)
    normal_audio(celery_client, bot_msg)
    logging.info("Audio celery tasks ended.")


def get_unique_clink(original_url: str, user_id: int):
    payment = Payment()
    settings = payment.get_user_settings(user_id)
    clink = channel.extract_canonical_link(original_url)
    try:
        # different user may have different resolution settings
        unique = "{}?p={}{}".format(clink, *settings[1:])
    except IndexError:
        unique = clink
    return unique


@app.task()
def direct_download_task(chat_id, message_id, url):
    logging.info("Direct download celery tasks started for %s", url)
    bot_msg = get_messages(chat_id, message_id)
    direct_normal_download(celery_client, bot_msg, url)
    logging.info("Direct download celery tasks ended.")


def forward_video(client, bot_msg, url: str):
    chat_id = bot_msg.chat.id
    unique = get_unique_clink(url, chat_id)
    cached_fid = redis.get_send_cache(unique)
    if not cached_fid:
        redis.update_metrics("cache_miss")
        return False

    res_msg: "Message" = upload_processor(client, bot_msg, url, cached_fid)
    obj = res_msg.document or res_msg.video or res_msg.audio or res_msg.animation or res_msg.photo

    caption, _ = gen_cap(bot_msg, url, obj)
    res_msg.edit_text(caption, reply_markup=gen_video_markup())
    bot_msg.edit_text(f"Download success!✅✅✅")
    redis.update_metrics("cache_hit")
    return True


def ytdl_download_entrance(client: Client, bot_msg: types.Message, url: str, mode=None):
    payment = Payment()
    chat_id = bot_msg.chat.id
    try:
        if forward_video(client, bot_msg, url):
            return
        mode = mode or payment.get_user_settings(chat_id)[-1]
        if ENABLE_CELERY and mode in [None, "Celery"]:
            async_task(ytdl_download_task, chat_id, bot_msg.message_id, url)
            # ytdl_download_task.delay(chat_id, bot_msg.message_id, url)
        else:
            ytdl_normal_download(client, bot_msg, url)
    except Exception as e:
        logging.error("Failed to download %s, error: %s", url, e)
        bot_msg.edit_text(f"Download failed!❌\n\n`{traceback.format_exc()[0:4000]}`", disable_web_page_preview=True)


def direct_download_entrance(client: Client, bot_msg: typing.Union[types.Message, typing.Coroutine], url: str):
    if ENABLE_CELERY:
        direct_normal_download(client, bot_msg, url)
        # direct_download_task.delay(bot_msg.chat.id, bot_msg.message_id, url)
    else:
        direct_normal_download(client, bot_msg, url)


def audio_entrance(client, bot_msg):
    if ENABLE_CELERY:
        async_task(audio_task, bot_msg.chat.id, bot_msg.message_id)
        # audio_task.delay(bot_msg.chat.id, bot_msg.message_id)
    else:
        normal_audio(client, bot_msg)


def direct_normal_download(client: Client, bot_msg: typing.Union[types.Message, typing.Coroutine], url: str):
    chat_id = bot_msg.chat.id
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36"
    }
    length = 0

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

        client.send_chat_action(chat_id, "upload_document")
        client.send_document(
            bot_msg.chat.id,
            filepath,
            caption=f"filesize: {sizeof_fmt(st_size)}",
            progress=upload_hook,
            progress_args=(bot_msg,),
        )
        bot_msg.edit_text("Download success!✅")


def normal_audio(client: Client, bot_msg: typing.Union[types.Message, typing.Coroutine]):
    chat_id = bot_msg.chat.id
    # fn = getattr(bot_msg.video, "file_name", None) or getattr(bot_msg.document, "file_name", None)
    status_msg: typing.Union[types.Message, typing.Coroutine] = bot_msg.reply_text(
        "Converting to audio...please wait patiently", quote=True
    )
    orig_url: str = re.findall(r"https?://.*", bot_msg.caption)[0]
    with tempfile.TemporaryDirectory(prefix="ytdl-") as tmp:
        client.send_chat_action(chat_id, "record_audio")
        # just try to download the audio using yt-dlp
        filepath = ytdl_download(orig_url, tmp, status_msg, hijack="bestaudio[ext=m4a]")
        status_msg.edit_text("Sending audio now...")
        client.send_chat_action(chat_id, "upload_audio")
        for f in filepath:
            client.send_audio(chat_id, f)
        status_msg.edit_text("✅ Conversion complete.")
        Redis().update_metrics("audio_success")


def get_dl_source():
    worker_name = os.getenv("WORKER_NAME")
    if worker_name:
        return f"Downloaded by  {worker_name}"
    return ""


def upload_transfer_sh(bm, paths: list) -> str:
    d = {p.name: (md5(p.name.encode("utf8")).hexdigest() + p.suffix, p.open("rb")) for p in paths}
    monitor = MultipartEncoderMonitor(MultipartEncoder(fields=d), lambda x: upload_hook(x.bytes_read, x.len, bm))
    headers = {"Content-Type": monitor.content_type}
    try:
        req = requests.post("https://transfer.sh", data=monitor, headers=headers)
        bm.edit_text(f"Download success!✅")
        return re.sub(r"https://", "\nhttps://", req.text)
    except requests.exceptions.RequestException as e:
        return f"Upload failed!❌\n\n```{e}```"


def flood_owner_message(client, ex):
    client.send_message(OWNER, f"CRITICAL INFO: {ex}")


def ytdl_normal_download(client: Client, bot_msg: typing.Union[types.Message, typing.Coroutine], url: str):
    chat_id = bot_msg.chat.id
    temp_dir = tempfile.TemporaryDirectory(prefix="ytdl-")

    video_paths = ytdl_download(url, temp_dir.name, bot_msg)
    logging.info("Download complete.")
    client.send_chat_action(chat_id, "upload_document")
    bot_msg.edit_text("Download complete. Sending now...")
    try:
        upload_processor(client, bot_msg, url, video_paths)
    except pyrogram.errors.Flood as e:
        logging.critical("FloodWait from Telegram: %s", e)
        client.send_message(
            chat_id,
            f"I'm being rate limited by Telegram. Your video will come after {e.x} seconds. Please wait patiently.",
        )
        flood_owner_message(client, e)
        time.sleep(e.x)
        upload_processor(client, bot_msg, url, video_paths)

    bot_msg.edit_text("Download success!✅")

    temp_dir.cleanup()


def generate_input_media(file_paths: list, cap: str) -> list:
    input_media = []
    for path in file_paths:
        mime = filetype.guess_mime(path)
        if "video" in mime:
            input_media.append(pyrogram.types.InputMediaVideo(media=path))
        elif "image" in mime:
            input_media.append(pyrogram.types.InputMediaPhoto(media=path))
        elif "audio" in mime:
            input_media.append(pyrogram.types.InputMediaAudio(media=path))
        else:
            input_media.append(pyrogram.types.InputMediaDocument(media=path))

    input_media[0].caption = cap
    return input_media


def upload_processor(client, bot_msg, url, vp_or_fid: typing.Union[str, list]):
    # raise pyrogram.errors.exceptions.FloodWait(13)
    # if is str, it's a file id; else it's a list of paths
    payment = Payment()
    chat_id = bot_msg.chat.id
    markup = gen_video_markup()
    if isinstance(vp_or_fid, list) and len(vp_or_fid) > 1:
        # just generate the first for simplicity, send as media group(2-20)
        cap, meta = gen_cap(bot_msg, url, vp_or_fid[0])
        res_msg = client.send_media_group(chat_id, generate_input_media(vp_or_fid, cap))
        # TODO no cache for now
        return res_msg[0]
    elif isinstance(vp_or_fid, list) and len(vp_or_fid) == 1:
        # normal download, just contains one file in video_paths
        vp_or_fid = vp_or_fid[0]
        cap, meta = gen_cap(bot_msg, url, vp_or_fid)
    else:
        # just a file id as string
        cap, meta = gen_cap(bot_msg, url, vp_or_fid)

    settings = payment.get_user_settings(chat_id)
    if ARCHIVE_ID and isinstance(vp_or_fid, pathlib.Path):
        chat_id = ARCHIVE_ID

    if settings[2] == "document":
        logging.info("Sending as document")
        try:
            # send as document could be sent as video even if it's a document
            res_msg = client.send_document(
                chat_id,
                vp_or_fid,
                caption=cap,
                progress=upload_hook,
                progress_args=(bot_msg,),
                reply_markup=markup,
                thumb=meta["thumb"],
                force_document=True,
            )
        except ValueError:
            logging.error("Retry to send as video")
            res_msg = client.send_video(
                chat_id,
                vp_or_fid,
                supports_streaming=True,
                caption=cap,
                progress=upload_hook,
                progress_args=(bot_msg,),
                reply_markup=markup,
                **meta,
            )
    elif settings[2] == "audio":
        logging.info("Sending as audio")
        res_msg = client.send_audio(
            chat_id,
            vp_or_fid,
            caption=cap,
            progress=upload_hook,
            progress_args=(bot_msg,),
        )
    else:
        # settings==video
        logging.info("Sending as video")
        try:
            res_msg = client.send_video(
                chat_id,
                vp_or_fid,
                supports_streaming=True,
                caption=cap,
                progress=upload_hook,
                progress_args=(bot_msg,),
                reply_markup=markup,
                **meta,
            )
        except Exception:
            # try to send as annimation, photo
            try:
                logging.warning("Retry to send as animation")
                res_msg = client.send_animation(
                    chat_id,
                    vp_or_fid,
                    caption=cap,
                    progress=upload_hook,
                    progress_args=(bot_msg,),
                    reply_markup=markup,
                    **meta,
                )
            except Exception:
                # this is likely a photo
                logging.warning("Retry to send as photo")
                res_msg = client.send_photo(
                    chat_id,
                    vp_or_fid,
                    caption=cap,
                    progress=upload_hook,
                    progress_args=(bot_msg,),
                )

    unique = get_unique_clink(url, bot_msg.chat.id)
    obj = res_msg.document or res_msg.video or res_msg.audio or res_msg.animation or res_msg.photo
    redis.add_send_cache(unique, getattr(obj, "file_id", None))
    redis.update_metrics("video_success")
    if ARCHIVE_ID and isinstance(vp_or_fid, pathlib.Path):
        client.forward_messages(bot_msg.chat.id, ARCHIVE_ID, res_msg.message_id)
    return res_msg


def gen_cap(bm, url, video_path):
    payment = Payment()
    chat_id = bm.chat.id
    user = bm.chat
    try:
        user_info = "@{}({})-{}".format(user.username or "N/A", user.first_name or "" + user.last_name or "", user.id)
    except Exception:
        user_info = ""

    if isinstance(video_path, pathlib.Path):
        meta = get_metadata(video_path)
        file_name = video_path.name
        file_size = sizeof_fmt(os.stat(video_path).st_size)
    else:
        file_name = getattr(video_path, "file_name", "")
        file_size = sizeof_fmt(getattr(video_path, "file_size", (2 << 2) + ((2 << 2) + 1) + (2 << 5)))
        meta = dict(
            width=getattr(video_path, "width", 0),
            height=getattr(video_path, "height", 0),
            duration=getattr(video_path, "duration", 0),
            thumb=getattr(video_path, "thumb", None),
        )
    free = payment.get_free_token(chat_id)
    pay = payment.get_pay_token(chat_id)
    if ENABLE_VIP:
        remain = f"Download token count: free {free}, pay {pay}"
    else:
        remain = ""
    worker = get_dl_source()
    cap = (
        f"{user_info}\n{file_name}\n\n{url}\n\nInfo: {meta['width']}x{meta['height']} {file_size}\t"
        f"{meta['duration']}s\n{remain}\n{worker}\n{bot_text.custom_text}"
    )
    return cap, meta


def gen_video_markup():
    markup = InlineKeyboardMarkup(
        [
            [  # First row
                InlineKeyboardButton(  # Generates a callback query when pressed
                    "convert to audio", callback_data="convert"
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


def async_task(task_name, *args):
    if not ENABLE_QUEUE:
        task_name.delay(*args)
        return

    t0 = time.time()
    inspect = app.control.inspect()
    worker_stats = inspect.stats()
    route_queues = []
    padding = math.ceil(sum([i["pool"]["max-concurrency"] for i in worker_stats.values()]) / len(worker_stats))
    for worker_name, stats in worker_stats.items():
        route = worker_name.split("@")[1]
        concurrency = stats["pool"]["max-concurrency"]
        route_queues.extend([route] * (concurrency + padding))
    destination = random.choice(route_queues)
    logging.info("Selecting worker %s from %s in %.2fs", destination, route_queues, time.time() - t0)
    task_name.apply_async(args=args, queue=destination)


def run_celery():
    worker_name = os.getenv("WORKER_NAME", "")
    argv = ["-A", "tasks", "worker", "--loglevel=info", "--pool=threads", f"--concurrency={WORKERS}", "-n", worker_name]
    if ENABLE_QUEUE:
        argv.extend(["-Q", worker_name])
    app.worker_main(argv)


def purge_tasks():
    count = app.control.purge()
    return f"purged {count} tasks."


if __name__ == "__main__":
    # celery_client.start()
    print("Bootstrapping Celery worker now.....")
    time.sleep(5)
    threading.Thread(target=run_celery, daemon=True).start()

    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(auto_restart, "interval", seconds=900)
    scheduler.start()

    idle()
    celery_client.stop()
