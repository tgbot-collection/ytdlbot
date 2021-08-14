#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - downloader.py
# 8/14/21 16:53
#

__author__ = "Benny <benny.think@gmail.com>"

import logging
import os
import pathlib
import subprocess
import traceback

import fakeredis
import filetype
import youtube_dl
from youtube_dl import DownloadError

r = fakeredis.FakeStrictRedis()
EXPIRE = 5


def sizeof_fmt(num: int, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def edit_text(bot_msg, text):
    key = bot_msg.message_id
    # if the key exists, we shouldn't send edit message
    if not r.exists(key):
        r.set(key, "ok", ex=EXPIRE)
        bot_msg.edit_text(text)


def download_hook(d: dict, bot_msg):
    if d['status'] == 'downloading':
        downloaded = d.get("downloaded_bytes", 0)
        total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
        filesize = sizeof_fmt(total)
        if total > 2 * 1024 * 1024 * 1024:
            raise Exception("\n\nYour video is too large. %s will exceed Telegram's max limit 2GiB" % filesize)

        percent = d.get("_percent_str", "N/A")
        speed = d.get("_speed_str", "N/A")
        text = f'[{filesize}]: Downloading {percent} - {downloaded}/{total} @ {speed}'
        edit_text(bot_msg, text)


def upload_hook(current, total, bot_msg):
    filesize = sizeof_fmt(total)
    text = f'[{filesize}]: Uploading {round(current / total * 100, 2)}% - {current}/{total}'
    edit_text(bot_msg, text)


def convert_to_mp4(resp: dict):
    default_type = ["video/x-flv"]
    if resp["status"]:
        mime = filetype.guess(resp["filepath"]).mime
        if mime in default_type:
            path = resp["filepath"]
            new_name = os.path.basename(path).split(".")[0] + ".mp4"
            new_file_path = os.path.join(os.path.dirname(path), new_name)
            cmd = "ffmpeg -i {} {}".format(path, new_file_path)
            logging.info("Detected %s, converting to mp4...", mime)
            subprocess.check_output(cmd.split())
            resp["filepath"] = new_file_path
            return resp


def ytdl_download(url, tempdir, bm) -> dict:
    response = dict(status=None, error=None, filepath=None)
    logging.info("Downloading for %s", url)
    output = os.path.join(tempdir, '%(title)s.%(ext)s')
    ydl_opts = {
        'progress_hooks': [lambda d: download_hook(d, bm)],
        'outtmpl': output,
        'restrictfilenames': True,
        'quiet': True
    }
    formats = [
        "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio",
        "bestvideo[vcodec^=avc]+bestaudio[acodec^=mp4a]/best[vcodec^=avc]/best",
        ""
    ]
    success, err = None, None
    for f in formats:
        if f:
            ydl_opts["format"] = f
        try:
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            success = True
        except DownloadError:
            err = traceback.format_exc()
            logging.error("Download failed for %s ", url)

        if success:
            response["status"] = True
            response["filepath"] = os.path.join(tempdir, [i for i in os.listdir(tempdir)][0])
            break
        else:
            response["status"] = False
            response["error"] = err
    # convert format if necessary
    convert_to_mp4(response)
    return response


def convert_flac(flac_name, tmp):
    flac_tmp = pathlib.Path(tmp.name).parent.joinpath(flac_name).as_posix()
    # ffmpeg -i input-video.avi -vn -acodec copy output-audio.m4a
    cmd = "ffmpeg -y -i {} -vn -acodec copy {}".format(tmp.name, flac_tmp)
    print(cmd)
    logging.info("converting to flac")
    subprocess.check_output(cmd.split())
    return flac_tmp
