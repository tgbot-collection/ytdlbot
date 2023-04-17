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
import shutil
import subprocess
import tempfile
import time
import uuid

import coloredlogs
import ffmpeg
import psutil

from flower_tasks import app

inspect = app.control.inspect()


def apply_log_formatter():
    coloredlogs.install(
        level=logging.INFO,
        fmt="[%(asctime)s %(filename)s:%(lineno)d %(levelname).1s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def customize_logger(logger: list):
    apply_log_formatter()
    for log in logger:
        logging.getLogger(log).setLevel(level=logging.INFO)


def sizeof_fmt(num: int, suffix="B"):
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, "Yi", suffix)


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

    def updates_too_long_detector(self):
        # If you're seeing this, that means you have logged more than 10 device
        # and the earliest account was kicked out. Restart the program could get you back in.
        indicators = [
            "types.UpdatesTooLong",
            "Got shutdown from remote",
            "Code is updated",
            'Retrying "messages.GetMessages"',
            "OSError: Connection lost",
            "[Errno -3] Try again",
            "MISCONF",
        ]
        for indicator in indicators:
            if indicator in self.logs:
                logging.warning("Potential crash detected by %s, it's time to commit suicide...", self.func_name())
                return True
        logging.debug("No crash detected.")

    def next_salt_detector(self):
        text = "Next salt in"
        if self.logs.count(text) >= 4:
            logging.warning("Potential crash detected by %s, it's time to commit suicide...", self.func_name())
            return True

    # def idle_detector(self):
    #     mtime = os.stat("/var/log/ytdl.log").st_mtime
    #     cur_ts = time.time()
    #     if cur_ts - mtime > 7200:
    #         logging.warning("Potential crash detected by %s, it's time to commit suicide...", self.func_name())
    #         return True


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
            logging.critical("Bye bye world!☠️")
            for item in pathlib.Path(tempfile.gettempdir()).glob("ytdl-*"):
                shutil.rmtree(item, ignore_errors=True)

            psutil.Process().kill()


def clean_tempfile():
    for item in pathlib.Path(tempfile.gettempdir()).glob("ytdl-*"):
        if time.time() - item.stat().st_ctime > 3600:
            shutil.rmtree(item, ignore_errors=True)


if __name__ == "__main__":
    auto_restart()
