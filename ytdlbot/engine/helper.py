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
from http import HTTPStatus
from io import StringIO

import ffmpeg
import ffpb
import filetype
import pyrogram
import requests
import yt_dlp
from bs4 import BeautifulSoup
from pyrogram import types
from tqdm import tqdm

from config import (
    AUDIO_FORMAT,
    CAPTION_URL_LENGTH_LIMIT,
    ENABLE_ARIA2,
    TG_NORMAL_MAX_SIZE,
)
from utils import get_metadata, shorten_url, sizeof_fmt


def ytdl_download(url: str, tempdir, bm, formats: list = None) -> list:
    output = pathlib.Path(tempdir, "%(title).70s.%(ext)s").as_posix()
    default_formats = [
        # webm , vp9 and av01 are not streamable on telegram, so we'll extract only mp4
        "bestvideo[ext=mp4][vcodec!*=av01][vcodec!*=vp09]+bestaudio[ext=m4a]/bestvideo+bestaudio",
        "bestvideo[vcodec^=avc]+bestaudio[acodec^=mp4a]/best[vcodec^=avc]/best",
        None,
    ]
    if formats:
        default_formats = formats + default_formats

    ydl_opts = {
        "progress_hooks": [lambda d: download_hook(d, bm)],
        "outtmpl": output,
        "restrictfilenames": False,
        "quiet": True,
    }
    if ENABLE_ARIA2:
        ydl_opts["external_downloader"] = "aria2c"
        ydl_opts["external_downloader_args"] = [
            "--min-split-size=1M",
            "--max-connection-per-server=16",
            "--max-concurrent-downloads=16",
            "--split=16",
        ]

    if url.startswith("https://drive.google.com"):
        # Always use the `source` format for Google Drive URLs.
        default_formats = ["source"]

    video_paths = None
    for f in default_formats:
        ydl_opts["format"] = f
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        video_paths = list(pathlib.Path(tempdir).glob("*"))
        break

    return video_paths


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
            edit_text(bot_msg, f"Converting {path.name} to mp4. Please wait.")
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


def get_caption(url, video_path):
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
        f"{file_name}\n\n{url_for_cap}\n\nInfo: {meta['width']}x{meta['height']} {file_size}\t" f"{meta['duration']}s\n"
    )
    return cap


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


def extract_canonical_link(url: str) -> str:
    # canonic link works for many websites. It will strip out unnecessary stuff
    props = ["canonical", "alternate", "shortlinkUrl"]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36"
    }
    cookie = {"CONSENT": "PENDING+197"}
    # send head request first
    r = requests.head(url, headers=headers, allow_redirects=True, cookies=cookie)
    if r.status_code != HTTPStatus.METHOD_NOT_ALLOWED and "text/html" not in r.headers.get("content-type", ""):
        # get content-type, if it's not text/html, there's no need to issue a GET request
        logging.warning("%s Content-type is not text/html, no need to GET for extract_canonical_link", url)
        return url

    html_doc = requests.get(url, headers=headers, cookies=cookie, timeout=5).text
    soup = BeautifulSoup(html_doc, "html.parser")
    for prop in props:
        element = soup.find(lambda tag: tag.name == "link" and tag.get("rel") == ["prop"])
        try:
            href = element["href"]
            if href not in ["null", "", None, "https://consent.youtube.com/m"]:
                return href
        except Exception as e:
            logging.debug("Canonical exception %s %s e", url, e)

    return url
