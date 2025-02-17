#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - __init__.py.py

from urllib.parse import urlparse

from engine.generic import YoutubeDownload
from engine.direct import DirectDownload
from engine.pixeldrain import pixeldrain_download
from engine.instagram import InstagramDownload
from engine.krakenfiles import krakenfiles_download


def youtube_entrance(client, bot_message, url):
    youtube = YoutubeDownload(client, bot_message, url)
    youtube.start()


def direct_entrance(client, bot_message, url):
    dl = DirectDownload(client, bot_message, url)
    dl.start()


def special_download_entrance(client, bot_message, url):
    """Specific link downloader"""
    domain = urlparse(url).hostname
    if "youtube.com" in domain or "youtu.be" in domain:
        raise ValueError("ERROR: For Youtube links, just send the link.")
    elif "www.instagram.com" in domain:
        dl = InstagramDownload(client, bot_message, url)
        dl.start()
    elif "pixeldrain.com" in domain:
        return pixeldrain_download(client, bot_message, url)
    elif "krakenfiles.com" in domain:
        return krakenfiles_download(client, bot_message, url)
    else:
        raise ValueError(f"Invalid URL: No specific link function found for {url}")
