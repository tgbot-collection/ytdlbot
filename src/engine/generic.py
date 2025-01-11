#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - generic.py

from pathlib import Path

import yt_dlp
from engine.base import BaseDownloader
from pyrogram import types

from database.model import get_download_settings


class YoutubeDownload(BaseDownloader):

    def _setup_formats(self) -> list | None:
        download = get_download_settings(self._user_id)
        formats = []
        # "high", "medium", "low", "audio", "custom"
        if download == "custom":
            # get format from ytdlp, send inlinekeyboard button to user so they can choose
            # another callback will be triggered to download the video
            available_options = {
                "480P": "best[height<=480]",
                "720P": "best[height<=720]",
                "1080P": "best[height<=1080]",
            }
            markup, temp_row = [], []
            for quality, data in available_options.items():
                temp_row.append(types.InlineKeyboardButton(quality, callback_data=data))
                if len(temp_row) == 3:  # Add a row every 3 buttons
                    markup.append(temp_row)
                    temp_row = []
            # Add any remaining buttons as the last row
            if temp_row:
                markup.append(temp_row)
            self._bot_msg.edit_text("Choose the format", reply_markup=types.InlineKeyboardMarkup(markup))
            return None
        if download == "audio":
            # download audio only
            formats.append("bestaudio")
        elif download == "high":
            # default config
            formats.extend(
                [
                    # webm , vp9 and av01 are not streamable on telegram, so we'll extract only mp4
                    "bestvideo[ext=mp4][vcodec!*=av01][vcodec!*=vp09]+bestaudio[ext=m4a]/bestvideo+bestaudio",
                    "bestvideo[vcodec^=avc]+bestaudio[acodec^=mp4a]/best[vcodec^=avc]/best",
                    None,
                ]
            )

        elif download == "medium":
            # download medium quality video
            formats.append("medium")
        elif download == "low":
            # download low quality video
            formats.append("worst")
        return formats

    def _download(self, formats) -> list:
        output = Path(self._tempdir, "%(title).70s.%(ext)s").as_posix()
        ydl_opts = {
            "progress_hooks": [lambda d: self.download_hook(d)],
            "outtmpl": output,
            "restrictfilenames": False,
            "quiet": True,
        }

        if self._url.startswith("https://drive.google.com"):
            # Always use the `source` format for Google Drive URLs.
            formats = ["source"] + formats

        files = None
        for f in formats:
            ydl_opts["format"] = f
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self._url])
            files = list(Path(self._tempdir).glob("*"))
            break

        return files

    def start(self, formats=None):
        # user can choose format by clicking on the button(custom config)
        default_formats = self._setup_formats()
        if formats is not None:
            # formats according to user choice
            default_formats = formats + self._setup_formats()
        self._download(default_formats)
        self._upload()
