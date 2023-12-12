#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - instagram.py
# 2023-12-12  17:42

import logging

import requests
from flask import Flask, request

from config import INSTAGRAM_SESSION
from utils import apply_log_formatter

apply_log_formatter()
app = Flask(__name__)


@app.route("/")
def index():
    url = request.args.get("url")

    logging.info("Requesting instagram download link for %s", url)
    cookies = {"sessionid": INSTAGRAM_SESSION}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
    }

    params = {"__a": "1", "__d": "dis"}

    try:
        data = requests.get(url, params=params, cookies=cookies, headers=headers).json()
    except Exception:
        logging.warning("Can't get instagram data for %s", url)
        return {}

    url_results = []
    if carousels := data["items"][0].get("carousel_media"):
        for carousel in carousels:
            if carousel.get("video_versions"):
                url_results.append(carousel["video_versions"][0]["url"])
            else:
                url_results.append(carousel["image_versions2"]["candidates"][0]["url"])

    elif video := data["items"][0].get("video_versions"):
        url_results.append(video[0]["url"])
    elif image := data["items"][0].get("image_versions2"):
        url_results.append(image["candidates"][0]["url"])
    else:
        logging.warning("Can't find any downloadable link for %s", url)
        return {}
    return {"data": url_results}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
