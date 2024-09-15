#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - utils.py
# 9/1/21 22:50
#

__author__ = "Benny <benny.think@gmail.com>"

import contextlib
import inspect as pyinspect
import logging
import os
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
import psutil

from config import TMPFILE_PATH
from flower_tasks import app

inspect = app.control.inspect()


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


def timeof_fmt(seconds: int):
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


def get_func_queue(func) -> int:
    try:
        count = 0
        data = getattr(inspect, func)() or {}
        for _, task in data.items():
            count += len(task)
        return count
    except Exception:
        return 0


def tail_log(f, lines=1, _buffer=4098):
    """Tail a file and get X lines from the end"""
    # placeholder for the lines found
    lines_found = []

    # block counter will be multiplied by buffer
    # to get the block size from the end
    block_counter = -1

    # loop until we find X lines
    while len(lines_found) < lines:
        try:
            f.seek(block_counter * _buffer, os.SEEK_END)
        except IOError:  # either file is too small, or too many lines requested
            f.seek(0)
            lines_found = f.readlines()
            break

        lines_found = f.readlines()

        # we found enough lines, get out
        # Removed this line because it was redundant the while will catch
        # it, I left it for history
        # if len(lines_found) > lines:
        #    break

        # decrement the block counter to get the
        # next X bytes
        block_counter -= 1

    return lines_found[-lines:]


class Detector:
    def __init__(self, logs: str):
        self.logs = logs

    @staticmethod
    def func_name():
        with contextlib.suppress(Exception):
            return pyinspect.stack()[1][3]
        return "N/A"

    def auth_key_detector(self):
        text = "Server sent transport error: 404 (auth key not found)"
        if self.logs.count(text) >= 3:
            logging.critical("auth key not found: %s", self.func_name())
            os.unlink("*.session")
            return True

    def updates_too_long_detector(self):
        # If you're seeing this, that means you have logged more than 10 device
        # and the earliest account was kicked out. Restart the program could get you back in.
        indicators = [
            "types.UpdatesTooLong",
            "Got shutdown from remote",
            "Code is updated",
            "OSError: Connection lost",
            "[Errno -3] Try again",
            "MISCONF",
        ]
        for indicator in indicators:
            if indicator in self.logs:
                logging.critical("kick out crash: %s", self.func_name())
                return True
        logging.debug("No crash detected.")

    def next_salt_detector(self):
        text = "Next salt in"
        if self.logs.count(text) >= 5:
            logging.critical("Next salt crash: %s", self.func_name())
            return True

    def connection_reset_detector(self):
        text = "Send exception: ConnectionResetError Connection lost"
        if self.logs.count(text) >= 5:
            logging.critical("connection lost: %s ", self.func_name())
            return True


def auto_restart():
    log_path = "/var/log/ytdl.log"
    if not os.path.exists(log_path):
        return
    with open(log_path) as f:
        logs = "".join(tail_log(f, lines=10))

    det = Detector(logs)
    method_list = [getattr(det, func) for func in dir(det) if func.endswith("_detector")]
    for method in method_list:
        if method():
            logging.critical("%s bye bye world!☠️", method)
            for item in pathlib.Path(TMPFILE_PATH or tempfile.gettempdir()).glob("ytdl-*"):
                shutil.rmtree(item, ignore_errors=True)
            time.sleep(5)
            psutil.Process().kill()


def clean_tempfile():
    for item in pathlib.Path(TMPFILE_PATH or tempfile.gettempdir()).glob("ytdl-*"):
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
    url_pattern = r'(https?://[^\s]+)'
    # Regular expression to match the new name after '-n'
    name_pattern = r'-n\s+([^\s]+)'

    # Find the URL in the message_text
    url_match = re.search(url_pattern, message_text)
    url = url_match.group(0) if url_match else None

    # Find the new name in the message_text
    name_match = re.search(name_pattern, message_text)
    new_name = name_match.group(1) if name_match else None

    return url, new_name


if __name__ == "__main__":
    auto_restart()
