#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - helper.py

import functools
import logging
import os
import pathlib
import re
import subprocess
import threading
import time
from io import StringIO

import ffpb
import filetype
from pyrogram import types
from tqdm import tqdm


def debounce(wait_seconds):
    """
    Thread-safe debounce decorator for functions that take a message with chat.id and msg.id attributes.
    The function will only be called if it hasn't been called with the same chat.id and msg.id in the last 'wait_seconds'.
    """

    def decorator(func):
        last_called = {}
        lock = threading.Lock()

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal last_called
            now = time.time()

            # Assuming the first argument is the message object with chat.id and msg.id
            bot_msg = args[0]
            key = (bot_msg.chat.id, bot_msg.id)

            with lock:
                if key not in last_called or now - last_called[key] >= wait_seconds:
                    last_called[key] = now
                    return func(*args, **kwargs)

        return wrapper

    return decorator


@debounce(5)
def edit_text(bot_msg: types.Message, text: str):
    bot_msg.edit_text(text)


def tqdm_progress(desc, total, finished, speed="", eta=""):
    def more(title, initial):
        if initial:
            return f"{title} {initial}"
        else:
            return ""

    f = StringIO()
    tqdm(
        total=total,
        initial=finished,
        file=f,
        ascii=False,
        unit_scale=True,
        ncols=30,
        bar_format="{l_bar}{bar} |{n_fmt}/{total_fmt} ",
    )
    raw_output = f.getvalue()
    tqdm_output = raw_output.split("|")
    progress = f"`[{tqdm_output[1]}]`"
    detail = tqdm_output[2].replace("[A", "")
    text = f"""
{desc}

{progress}
{detail}
{more("Speed:", speed)}
{more("ETA:", eta)}
    """
    f.close()
    return text


def remove_bash_color(text):
    return re.sub(r"\u001b|\[0;94m|\u001b\[0m|\[0;32m|\[0m|\[0;33m", "", text)


def convert_to_mp4(video_paths: list, bot_msg):
    default_type = ["video/x-flv", "video/webm"]
    # all_converted = []
    for path in video_paths:
        # if we can't guess file type, we assume it's video/mp4
        mime = getattr(filetype.guess(path), "mime", "video/mp4")
        if mime in default_type:
            if not can_convert_mp4(path, bot_msg.chat.id):
                logging.warning("Conversion abort for %s", bot_msg.chat.id)
                bot_msg._client.send_message(bot_msg.chat.id, "Can't convert your video. ffmpeg has been disabled.")
                break
            edit_text(bot_msg, f"{current_time()}: Converting {path.name} to mp4. Please wait.")
            new_file_path = path.with_suffix(".mp4")
            logging.info("Detected %s, converting to mp4...", mime)
            run_ffmpeg_progressbar(["ffmpeg", "-y", "-i", path, new_file_path], bot_msg)
            index = video_paths.index(path)
            video_paths[index] = new_file_path


class ProgressBar(tqdm):
    b = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot_msg = self.b

    def update(self, n=1):
        super().update(n)
        t = tqdm_progress("Converting...", self.total, self.n)
        edit_text(self.bot_msg, t)


def run_ffmpeg_progressbar(cmd_list: list, bm):
    cmd_list = cmd_list.copy()[1:]
    ProgressBar.b = bm
    ffpb.main(cmd_list, tqdm=ProgressBar)


def gen_video_markup():
    markup = types.InlineKeyboardMarkup(
        [
            [  # First row
                types.InlineKeyboardButton(  # Generates a callback query when pressed
                    "convert to audio", callback_data="convert"
                )
            ]
        ]
    )
    return markup


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

    if worker_name := os.getenv("WORKER_NAME"):
        worker = f"Downloaded by  {worker_name}"
    else:
        worker = ""
    # Shorten the URL if necessary
    try:
        if len(url) > CAPTION_URL_LENGTH_LIMIT:
            url_for_cap = shorten_url(url, CAPTION_URL_LENGTH_LIMIT)
        else:
            url_for_cap = url
    except Exception as e:
        logging.warning(f"Error shortening URL: {e}")
        url_for_cap = url

    cap = (
        f"{user_info}\n{file_name}\n\n{url_for_cap}\n\nInfo: {meta['width']}x{meta['height']} {file_size}\t"
        f"{meta['duration']}s\n{remain}\n{worker}\n{bot_text.custom_text}"
    )
    return cap, meta


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


def download_hook(d: dict, bot_msg):
    if d["status"] == "downloading":
        downloaded = d.get("downloaded_bytes", 0)
        total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)

        if total > TG_NORMAL_MAX_SIZE:
            msg = f"Your download file size {sizeof_fmt(total)} is too large for Telegram."
            raise Exception(msg)

        # percent = remove_bash_color(d.get("_percent_str", "N/A"))
        speed = remove_bash_color(d.get("_speed_str", "N/A"))
        eta = remove_bash_color(d.get("_eta_str", d.get("eta")))
        text = tqdm_progress("Downloading...", total, downloaded, speed, eta)
        # debounce in here
        edit_text(bot_msg, text)


def upload_hook(current, total, bot_msg):
    text = tqdm_progress("Uploading...", total, current)
    edit_text(bot_msg, text)


def convert_audio_format(video_paths: list, bm):
    # 1. file is audio, default format
    # 2. file is video, default format
    # 3. non default format

    for path in video_paths:
        streams = ffmpeg.probe(path)["streams"]
        if AUDIO_FORMAT is None and len(streams) == 1 and streams[0]["codec_type"] == "audio":
            logging.info("%s is audio, default format, no need to convert", path)
        elif AUDIO_FORMAT is None and len(streams) >= 2:
            logging.info("%s is video, default format, need to extract audio", path)
            audio_stream = {"codec_name": "m4a"}
            for stream in streams:
                if stream["codec_type"] == "audio":
                    audio_stream = stream
                    break
            ext = audio_stream["codec_name"]
            new_path = path.with_suffix(f".{ext}")
            run_ffmpeg_progressbar(["ffmpeg", "-y", "-i", path, "-vn", "-acodec", "copy", new_path], bm)
            path.unlink()
            index = video_paths.index(path)
            video_paths[index] = new_path
        else:
            logging.info("Not default format, converting %s to %s", path, AUDIO_FORMAT)
            new_path = path.with_suffix(f".{AUDIO_FORMAT}")
            run_ffmpeg_progressbar(["ffmpeg", "-y", "-i", path, new_path], bm)
            path.unlink()
            index = video_paths.index(path)
            video_paths[index] = new_path


def split_large_video(video_paths: list):
    original_video = None
    split = False
    for original_video in video_paths:
        size = os.stat(original_video).st_size
        if size > TG_NORMAL_MAX_SIZE:
            split = True
            logging.warning("file is too large %s, splitting...", size)
            subprocess.check_output(f"sh split-video.sh {original_video} {TG_NORMAL_MAX_SIZE * 0.95} ".split())
            os.remove(original_video)

    if split and original_video:
        return [i for i in pathlib.Path(original_video).parent.glob("*")]
