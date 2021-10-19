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
import time

import fakeredis
import filetype

if os.getenv("downloader") == "youtube-dl":
    import youtube_dl as ytdl
    from youtube_dl import DownloadError
else:
    import yt_dlp as ytdl
    from yt_dlp import DownloadError

from config import ENABLE_VIP
from limit import VIP, Redis
from utils import apply_log_formatter

r = fakeredis.FakeStrictRedis()
EXPIRE = 5
apply_log_formatter()


def sizeof_fmt(num: int, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def edit_text(bot_msg, text):
    key = f"{bot_msg.chat.id}-{bot_msg.message_id}"
    # if the key exists, we shouldn't send edit message
    if not r.exists(key):
        r.set(key, "ok", ex=EXPIRE)
        bot_msg.edit_text(text)


def download_hook(d: dict, bot_msg):
    if d['status'] == 'downloading':
        downloaded = d.get("downloaded_bytes", 0)
        total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
        # total = 0
        filesize = sizeof_fmt(total)
        max_size = 2 * 1024 * 1024 * 1024
        if total > max_size:
            raise ValueError(f"\nYour video is too large. "
                             f"{filesize} will exceed Telegram's max limit {sizeof_fmt(max_size)}")

        percent = d.get("_percent_str", "N/A")
        speed = d.get("_speed_str", "N/A")
        if ENABLE_VIP:
            result, err_msg = check_quota(total, bot_msg.chat.id)
            if result is False:
                raise ValueError(err_msg)
        text = f'[{filesize}]: Downloading {percent} - {downloaded}/{total} @ {speed}'
        edit_text(bot_msg, text)


def upload_hook(current, total, bot_msg):
    filesize = sizeof_fmt(total)
    text = f'[{filesize}]: Uploading {round(current / total * 100, 2)}% - {current}/{total}'
    edit_text(bot_msg, text)


def check_quota(file_size, chat_id) -> ("bool", "str"):
    remain, _, ttl = VIP().check_remaining_quota(chat_id)
    if file_size > remain:
        refresh_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ttl + time.time()))
        err = f"Quota exceed, you have {sizeof_fmt(remain)} remaining, " \
              f"but you want to download a video with {sizeof_fmt(file_size)} in size. \n" \
              f"Try again in {ttl} seconds({refresh_time})"
        logging.warning(err)
        Redis().update_metrics("quota_exceed")
        return False, err
    else:
        return True, ""


def convert_to_mp4(resp: dict):
    default_type = ["video/x-flv"]
    if resp["status"]:
        # all_converted = []
        for path in resp["filepath"]:
            mime = filetype.guess(path).mime
            if mime in default_type:
                new_name = os.path.basename(path).split(".")[0] + ".mp4"
                new_file_path = os.path.join(os.path.dirname(path), new_name)
                cmd = ["ffmpeg", "-i", path, new_file_path]
                logging.info("Detected %s, converting to mp4...", mime)
                subprocess.check_output(cmd)
                index = resp["filepath"].index(path)
                resp["filepath"][index] = new_file_path

        return resp


def ytdl_download(url, tempdir, bm) -> dict:
    chat_id = bm.chat.id
    response = {"status": True, "error": "", "filepath": []}
    output = os.path.join(tempdir, '%(title).50s.%(ext)s')
    ydl_opts = {
        'progress_hooks': [lambda d: download_hook(d, bm)],
        'outtmpl': output,
        'restrictfilenames': False,
        'quiet': True
    }
    formats = [
        "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio",
        "bestvideo[vcodec^=avc]+bestaudio[acodec^=mp4a]/best[vcodec^=avc]/best",
        ""
    ]
    # TODO it appears twitter download on macOS will fail. Don't know why...Linux's fine.
    for f in formats:
        if f:
            ydl_opts["format"] = f
        try:
            logging.info("Downloading for %s with format %s", url, f)
            with ytdl.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            response["status"] = True
            response["error"] = ""
            break

        except DownloadError as e:
            err = str(e)
            logging.error("Download failed for %s ", url)
            response["status"] = False
            response["error"] = err
            # can't return here
        except ValueError as e:
            response["status"] = False
            response["error"] = str(e)
        except Exception as e:
            logging.error("UNKNOWN EXCEPTION: %s", e)

    logging.info("%s - %s", url, response)
    if response["status"] is False:
        return response

    for i in os.listdir(tempdir):
        p: "str" = os.path.join(tempdir, i)
        file_size = os.stat(p).st_size
        if ENABLE_VIP:
            remain, _, ttl = VIP().check_remaining_quota(chat_id)
            result, err_msg = check_quota(file_size, chat_id)
        else:
            result, err_msg = True, ""
        if result is False:
            response["status"] = False
            response["error"] = err_msg
        else:
            VIP().use_quota(bm.chat.id, file_size)
            response["status"] = True
            response["filepath"].append(p)

    # convert format if necessary
    convert_to_mp4(response)
    return response


def convert_flac(flac_name, tmp):
    logging.info("converting to flac")
    flac_tmp = pathlib.Path(tmp.name).parent.joinpath(flac_name).as_posix()
    cmd_list = ["ffmpeg", "-y", "-i", tmp.name, "-vn", "-acodec", "copy", flac_tmp]
    logging.info("CMD: %s", cmd_list)
    subprocess.check_output(cmd_list)
    return flac_tmp
