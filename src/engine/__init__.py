#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - __init__.py.py

from urllib.parse import urlparse

from engine.generic import YoutubeDownload


def youtube_entrance(client, bot_message, url):
    youtube = YoutubeDownload(client, bot_message, url)
    youtube.start()


def special_download_entrance(url: str, tempdir: str, bm, **kwargs) -> list:
    """Specific link downloader"""
    domain = urlparse(url).hostname
    if "youtube.com" in domain or "youtu.be" in domain:
        raise ValueError("ERROR: This is ytdl bot for Youtube links just send the link.")
    elif "www.instagram.com" in domain:
        return instagram(url, tempdir, bm, **kwargs)
    elif "pixeldrain.com" in domain:
        return pixeldrain(url, tempdir, bm, **kwargs)
    elif "krakenfiles.com" in domain:
        return krakenfiles(url, tempdir, bm, **kwargs)
    else:
        raise ValueError(f"Invalid URL: No specific link function found for {url}")
