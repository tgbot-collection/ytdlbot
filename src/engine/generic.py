#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - generic.py

import logging
import os
from pathlib import Path

import yt_dlp

from config import AUDIO_FORMAT
from utils import is_youtube
from database.model import get_format_settings, get_quality_settings
from engine.base import BaseDownloader


def match_filter(info_dict):
    if info_dict.get("is_live"):
        raise NotImplementedError("Skipping live video")
    return None  # Allow download for non-live videos


class YoutubeDownload(BaseDownloader):
    @staticmethod
    def get_format(m):
        return [
            f"bestvideo[ext=mp4][height={m}]+bestaudio[ext=m4a]",
            f"bestvideo[vcodec^=avc][height={m}]+bestaudio[acodec^=mp4a]/best[vcodec^=avc]/best",
        ]

    def _setup_formats(self) -> list | None:
        if not is_youtube(self._url):
            return [None]

        quality, format_ = get_quality_settings(self._chat_id), get_format_settings(self._chat_id)
        # quality: high, medium, low, custom
        # format: audio, video, document
        formats = []
        defaults = [
            # webm , vp9 and av01 are not streamable on telegram, so we'll extract only mp4
            "bestvideo[ext=mp4][vcodec!*=av01][vcodec!*=vp09]+bestaudio[ext=m4a]/bestvideo+bestaudio",
            "bestvideo[vcodec^=avc]+bestaudio[acodec^=mp4a]/best[vcodec^=avc]/best",
            None,
        ]
        audio = AUDIO_FORMAT or "m4a"
        maps = {
            "high-audio": [f"bestaudio[ext={audio}]"],
            "high-video": defaults,
            "high-document": defaults,
            "medium-audio": [f"bestaudio[ext={audio}]"],  # no mediumaudio :-(
            "medium-video": self.get_format(720),
            "medium-document": self.get_format(720),
            "low-audio": [f"bestaudio[ext={audio}]"],
            "low-video": self.get_format(480),
            "low-document": self.get_format(480),
            "custom-audio": "",
            "custom-video": "",
            "custom-document": "",
        }

        if quality == "custom":
            pass
            # TODO not supported yet
            # get format from ytdlp, send inlinekeyboard button to user so they can choose
            # another callback will be triggered to download the video
            # available_options = {
            #     "480P": "best[height<=480]",
            #     "720P": "best[height<=720]",
            #     "1080P": "best[height<=1080]",
            # }
            # markup, temp_row = [], []
            # for quality, data in available_options.items():
            #     temp_row.append(types.InlineKeyboardButton(quality, callback_data=data))
            #     if len(temp_row) == 3:  # Add a row every 3 buttons
            #         markup.append(temp_row)
            #         temp_row = []
            # # Add any remaining buttons as the last row
            # if temp_row:
            #     markup.append(temp_row)
            # self._bot_msg.edit_text("Choose the format", reply_markup=types.InlineKeyboardMarkup(markup))
            # return None

        formats.extend(maps[f"{quality}-{format_}"])
        # extend default formats if not high*
        if quality != "high":
            formats.extend(defaults)
        return formats

    def _download(self, formats) -> list:
        output = Path(self._tempdir.name, "%(title).70s.%(ext)s").as_posix()
        ydl_opts = {
            "progress_hooks": [lambda d: self.download_hook(d)],
            "outtmpl": output,
            "restrictfilenames": False,
            "quiet": True,
            "match_filter": match_filter,
        }
        # setup cookies for youtube only
        if is_youtube(self._url):
            # use cookies from browser firstly
            if browsers := os.getenv("BROWSERS"):
                ydl_opts["cookiesfrombrowser"] = browsers.split(",")
            if os.path.isfile("youtube-cookies.txt") and os.path.getsize("youtube-cookies.txt") > 100:
                ydl_opts["cookiefile"] = "youtube-cookies.txt"
            # try add extract_args if present
            if potoken := os.getenv("POTOKEN"):
                ydl_opts["extractor_args"] = {"youtube": ["player-client=web,default", f"po_token=web+{potoken}"]}
                # for new version? https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide
                # ydl_opts["extractor_args"] = {
                #     "youtube": [f"po_token=web.player+{potoken}", f"po_token=web.gvs+{potoken}"]
                # }

        if self._url.startswith("https://drive.google.com"):
            # Always use the `source` format for Google Drive URLs.
            formats = ["source"] + formats

        files = None
        for f in formats:
            ydl_opts["format"] = f
            logging.info("yt-dlp options: %s", ydl_opts)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self._url])
            files = list(Path(self._tempdir.name).glob("*"))
            break

        return files

    def _start(self, formats=None):
        # start download and upload, no cache hit
        # user can choose format by clicking on the button(custom config)
        default_formats = self._setup_formats()
        if formats is not None:
            # formats according to user choice
            default_formats = formats + self._setup_formats()
        self._download(default_formats)
        self._upload()
