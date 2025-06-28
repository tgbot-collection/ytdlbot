#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - __init__.py.py

from urllib.parse import urlparse
from typing import Any, Callable

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


# --- Handler for the Instagram class, to make the interface consistent ---
def instagram_handler(client: Any, bot_message: Any, url: str) -> None:
    """A wrapper to handle the InstagramDownload class."""
    downloader = InstagramDownload(client, bot_message, url)
    downloader.start()

DOWNLOADER_MAP: dict[str, Callable[[Any, Any, str], Any]] = {
    "pixeldrain.com": pixeldrain_download,
    "krakenfiles.com": krakenfiles_download,
    "instagram.com": instagram_handler,
}

def special_download_entrance(client: Any, bot_message: Any, url: str) -> Any:
    try:
        hostname = urlparse(url).hostname
        if not hostname:
            raise ValueError(f"Could not parse a valid hostname from URL: {url}")
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid URL format: {url}") from e

    # Handle the special case for YouTube URLs first.
    if hostname.endswith("youtube.com") or hostname == "youtu.be":
        raise ValueError("ERROR: For YouTube links, just send the link directly.")

    # Iterate through the map to find a matching handler.
    for domain_suffix, handler_function in DOWNLOADER_MAP.items():
        if hostname.endswith(domain_suffix):
            return handler_function(client, bot_message, url)

    raise ValueError(f"Invalid URL: No specific downloader found for {hostname}")
