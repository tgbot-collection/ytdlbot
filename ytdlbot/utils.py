#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - utils.py
# 9/1/21 22:50
#

__author__ = "Benny <benny.think@gmail.com>"

import logging
import pathlib
import subprocess
import time
import uuid

import ffmpeg

from db import MySQL


def apply_log_formatter():
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s %(filename)s:%(lineno)d %(levelname).1s] %(message)s',
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def customize_logger(logger: "list"):
    apply_log_formatter()
    for log in logger:
        # TODO: bug fix: lost response sometime.
        logging.getLogger(log).setLevel(level=logging.INFO)


def get_user_settings(user_id: "str") -> "tuple":
    db = MySQL()
    cur = db.cur
    cur.execute("SELECT * FROM settings WHERE user_id = %s", (user_id,))
    data = cur.fetchone()
    if data is None:
        return 100, "high", "video"
    return data


def set_user_settings(user_id: int, field: "str", value: "str"):
    db = MySQL()
    cur = db.cur
    cur.execute("SELECT * FROM settings WHERE user_id = %s", (user_id,))
    data = cur.fetchone()
    if data is None:
        resolution = method = ""
        if field == "resolution":
            method = "video"
            resolution = value
        if field == "method":
            method = value
            resolution = "high"
        cur.execute("INSERT INTO settings VALUES (%s,%s,%s)", (user_id, resolution, method))
    else:
        cur.execute(f"UPDATE settings SET {field} =%s WHERE user_id = %s", (value, user_id))
    db.con.commit()


def is_youtube(url: "str"):
    if url.startswith("https://www.youtube.com/") or url.startswith("https://youtu.be/"):
        return True


def adjust_formats(user_id: "str", url: "str", formats: "list"):
    # high: best quality, 720P, 1080P, 2K, 4K, 8K
    # medium: 480P
    # low: 360P+240P
    mapping = {"high": [], "medium": [480], "low": [240, 360]}
    settings = get_user_settings(user_id)
    if settings and is_youtube(url):
        for m in mapping.get(settings[1], []):
            formats.insert(0, f"bestvideo[ext=mp4][height={m}]+bestaudio[ext=m4a]")
            formats.insert(1, f"bestvideo[vcodec^=avc][height={m}]+bestaudio[acodec^=mp4a]/best[vcodec^=avc]/best")


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

    thumb = pathlib.Path(video_path).parent.joinpath(f"{uuid.uuid4().hex}-thunmnail.png").as_posix()
    ffmpeg.input(video_path, ss=duration / 2).filter('scale', width, -1).output(thumb, vframes=1).run()
    return dict(height=height, width=width, duration=duration, thumb=thumb)


def current_time():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def get_revision():
    revision = subprocess.check_output("git -C ../ rev-parse --short HEAD".split()).decode("u8").replace("\n", "")
    return revision
