#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - utils.py
# 9/1/21 22:50
#

__author__ = "Benny <benny.think@gmail.com>"

import contextlib
import logging
import pathlib
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from http.cookiejar import MozillaCookieJar
from urllib.parse import quote_plus

import coloredlogs
import ffmpeg

from config import TMPFILE_PATH


def apply_log_formatter():
    coloredlogs.install(
        level=logging.INFO,
        fmt="[%(asctime)s %(filename)s:%(lineno)d %(levelname).1s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def customize_logger(logger: list):
    for log in logger:
        logging.getLogger(log).setLevel(level=logging.INFO)


def sizeof_fmt(num: int, suffix="B"):
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, "Yi", suffix)


def timeof_fmt(seconds: int | float):
    periods = [("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]
    result = ""
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            result += f"{int(period_value)}{period_name}"
    return result


def is_youtube(url: str):
    if url.startswith("https://www.youtube.com/") or url.startswith("https://youtu.be/"):
        return True


def adjust_formats(user_id: int, url: str, formats: list, hijack=None):
    from database import MySQL

    # high: best quality 1080P, 2K, 4K, 8K
    # medium: 720P
    # low: 480P
    if hijack:
        formats.insert(0, hijack)
        return

    mapping = {"high": [], "medium": [720], "low": [480]}
    settings = MySQL().get_user_settings(user_id)
    if settings and is_youtube(url):
        for m in mapping.get(settings[1], []):
            formats.insert(0, f"bestvideo[ext=mp4][height={m}]+bestaudio[ext=m4a]")
            formats.insert(1, f"bestvideo[vcodec^=avc][height={m}]+bestaudio[acodec^=mp4a]/best[vcodec^=avc]/best")

    if settings[2] == "audio":
        formats.insert(0, "bestaudio[ext=m4a]")

    if settings[2] == "document":
        formats.insert(0, None)


def get_metadata(video_path):
    width, height, duration = 1280, 720, 0
    try:
        video_streams = ffmpeg.probe(video_path, select_streams="v")
        for item in video_streams.get("streams", []):
            height = item["height"]
            width = item["width"]
        duration = int(float(video_streams["format"]["duration"]))
    except Exception as e:
        logging.error(e)
    try:
        thumb = pathlib.Path(video_path).parent.joinpath(f"{uuid.uuid4().hex}-thunmnail.png").as_posix()
        ffmpeg.input(video_path, ss=duration / 2).filter("scale", width, -1).output(thumb, vframes=1).run()
    except ffmpeg._run.Error:
        thumb = None

    return dict(height=height, width=width, duration=duration, thumb=thumb)


def current_time(ts=None):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def get_revision():
    with contextlib.suppress(subprocess.SubprocessError):
        return subprocess.check_output("git -C ../ rev-parse --short HEAD".split()).decode("u8").replace("\n", "")
    return "unknown"


def clean_tempfile():
    patterns = ["ytdl*", "spdl*", "leech*", "direct*"]
    temp_path = pathlib.Path(TMPFILE_PATH or tempfile.gettempdir())

    for pattern in patterns:
        for item in temp_path.glob(pattern):
            if time.time() - item.stat().st_ctime > 3600:
                shutil.rmtree(item, ignore_errors=True)


def parse_cookie_file(cookiefile):
    jar = MozillaCookieJar(cookiefile)
    jar.load()
    return {cookie.name: cookie.value for cookie in jar}


def extract_code_from_instagram_url(url):
    # Regular expression patterns
    patterns = [r"/p/([a-zA-Z0-9_-]+)/", r"/reel/([a-zA-Z0-9_-]+)/"]  # Posts  # Reels

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


def shorten_url(url, CAPTION_URL_LENGTH_LIMIT):
    # Shortens a URL by cutting it to a specified length.
    shortened_url = url[: CAPTION_URL_LENGTH_LIMIT - 3] + "..."

    return shortened_url


def extract_filename(response):
    try:
        content_disposition = response.headers.get("content-disposition")
        if content_disposition:
            filename = re.findall("filename=(.+)", content_disposition)[0]
            return filename
    except (TypeError, IndexError):
        pass  # Handle potential exceptions during extraction

    # Fallback if Content-Disposition header is missing
    filename = response.url.rsplit("/")[-1]
    if not filename:
        filename = quote_plus(response.url)
    return filename


def extract_url_and_name(message_text):
    # Regular expression to match the URL
    url_pattern = r"(https?://[^\s]+)"
    # Regular expression to match the new name after '-n'
    name_pattern = r"-n\s+([^\s]+)"

    # Find the URL in the message_text
    url_match = re.search(url_pattern, message_text)
    url = url_match.group(0) if url_match else None

    # Find the new name in the message_text
    name_match = re.search(name_pattern, message_text)
    new_name = name_match.group(1) if name_match else None

    return url, new_name
