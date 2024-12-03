#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - generic.py

from base import BaseDownloader
from pyrogram import types

from database.model import get_download_settings


class YoutubeDownload(BaseDownloader):

    def _setup_formats(self):
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
            return
        if download == "audio":
            # download audio only
            formats.append("bestaudio")
        elif download == "high":
            # download high quality video
            formats.append("best")
        elif download == "medium":
            # download medium quality video
            formats.append("medium")
        elif download == "low":
            # download low quality video
            formats.append("worst")
        return formats

    def _download(self, formats):
        pass

    def start(self, formats=None):
        if formats is None:
            formats = self._setup_formats()
        self._download(formats)
        self._upload()
