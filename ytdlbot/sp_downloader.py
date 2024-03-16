#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - sp_downloader.py
# 3/16/24 16:32
#

__author__ = "Benny <benny.think@gmail.com>, SanujaNS <sanujas@sanuja.biz>"

import pathlib
import logging
import traceback
import re
import requests
from tqdm import tqdm
import json
from bs4 import BeautifulSoup
from urllib.parse import parse_qs, urlparse
import filetype
import yt_dlp as ytdl

from config import (
    ENABLE_ARIA2,
    IPv6,
)

user_agent = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.128 Safari/537.36"
)


def sp_dl(url: str, tempdir: str):
    """Specific link downloader"""
    domain = urlparse(url).hostname
    if not any(
        x in domain
        for x in [
            "www.instagram.com",
            "pixeldrain.com",
            "mediafire.com",
        ]
    ):
        return False
    if "www.instagram.com" in domain:
        return instagram(url, tempdir)
    elif "pixeldrain.com" in domain:
        return pixeldrain(url, tempdir)
    elif "www.xasiat.com" in domain:
        return xasiat(url, tempdir)


def sp_ytdl_download(url: str, tempdir: str):
    output = pathlib.Path(tempdir, "%(title).70s.%(ext)s").as_posix()
    ydl_opts = {
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
    formats = [
        # webm , vp9 and av01 are not streamable on telegram, so we'll extract mp4 and not av01 codec
        "bestvideo[ext=mp4][vcodec!*=av01][vcodec!*=vp09]+bestaudio[ext=m4a]/bestvideo+bestaudio",
        "bestvideo[vcodec^=avc]+bestaudio[acodec^=mp4a]/best[vcodec^=avc]/best",
        None,
    ]

    address = ["::", "0.0.0.0"] if IPv6 else [None]
    error = None
    video_paths = None
    for format_ in formats:
        ydl_opts["format"] = format_
        for addr in address:
            # IPv6 goes first in each format
            ydl_opts["source_address"] = addr
            try:
                logging.info("Downloading for %s with format %s", url, format_)
                with ytdl.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                video_paths = list(pathlib.Path(tempdir).glob("*"))
                break
            except Exception:
                error = traceback.format_exc()
                logging.error("Download failed for %s - %s, try another way", format_, url)
        if error is None:
            break

    if not video_paths:
        raise Exception(error)

    return video_paths


def instagram(url: str, tempdir: str):
    resp = requests.get(f"http://192.168.6.1:15000/?url={url}").json()
    if url_results := resp.get("data"):
        for link in url_results:
            content = requests.get(link, stream=True).content
            ext = filetype.guess_extension(content)
            save_path = pathlib.Path(tempdir, f"{id(link)}.{ext}")
            with open(save_path, "wb") as f:
                f.write(content)

        return True

def pixeldrain(url: str, tempdir: str):
    user_page_url_regex = r'https://pixeldrain.com/u/(\w+)'
    match = re.match(user_page_url_regex, url)
    if match:
        url = 'https://pixeldrain.com/api/file/{}?download'.format(match.group(1))
        sp_ytdl_download(url, tempdir)
    else:
        return url
    
    return True

def xasiat(url: str, tempdir: str):
    return False