#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - generic.py

from base import BaseDownloader

from database.model import get_download_settings


class YoutubeDownload(BaseDownloader):

    def _setup_formats(self):
        download = get_download_settings(self._user_id)
        formats = []
        # "high", "medium", "low", "audio", "custom"
        if download == "custom":
            # get format from ytdlp, send inlinekeyboard button to user so they can choose
            # another callback will be triggered to download the video
            self._client.send_message(self._user_id, "Choose the format", reply_to_message_id=self._id)
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
