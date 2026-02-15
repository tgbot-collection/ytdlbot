#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - test.py

import yt_dlp
from config import PROXY

url = "https://www.youtube.com/watch?v=e19kTVgb2c8"
opts = {
    "cookiefile": "cookies.txt",
    "cookiesfrombrowser": ["firefox"],
}
if PROXY:
    opts["proxy"] = PROXY

with yt_dlp.YoutubeDL(opts) as ydl:
    ydl.download([url])
