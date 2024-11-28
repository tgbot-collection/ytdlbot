#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - leech.py

import logging
import os
import pathlib
import subprocess
import tempfile

import filetype
from base import BaseDownloader
from pyrogram import enums

from config import ENABLE_ARIA2, TMPFILE_PATH


class DirectDownloader(BaseDownloader):

    def start(self):
        pass

    def _setup_formats(self):
        pass

    def _requests_download(self):
        pass

    def _aria2_download(self):
        chat_id = self._bot_msg.chat.id
        temp_dir = tempfile.TemporaryDirectory(prefix="ytdl-aria2-", dir=TMPFILE_PATH)
        tempdir = temp_dir.name
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        response = None
        video_paths = None
        # Download process using aria2c
        try:
            self._bot_msg.edit_text(f"Download Starting...", disable_web_page_preview=True)
            # Command to engine the link using aria2c
            command = [
                "aria2c",
                "-U",
                ua,
                "--max-tries=5",
                "--console-log-level=warn",
                "-d",
                tempdir,
                self._url,
            ]
            # Run the command using subprocess.Popen
            process = subprocess.Popen(command, bufsize=0, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            line = ""
            max_iterations = 100  # Set a reasonable maximum number of iterations
            iteration = 0

            while process.poll() is None and iteration < max_iterations:
                line = process.stdout.readline().decode("utf-8")
                if line.startswith("[#"):
                    line = line.strip()
                    self._bot_msg.edit_text(f"Downloading... \n\n`{line}`", disable_web_page_preview=True)
                    break
                iteration += 1

            if iteration >= max_iterations:
                self._bot_msg.edit_text("Something went wrong. Please try again.", disable_web_page_preview=True)
        except Exception as e:
            self._bot_msg.edit_text(f"Download failed!❌\n\n`{e}`", disable_web_page_preview=True)
            return
        # Get filename and extension correctly after engine
        filepath = list(pathlib.Path(tempdir).glob("*"))
        file_path_obj = filepath[0]
        path_obj = pathlib.Path(file_path_obj)
        filename = path_obj.name
        logging.info("Downloaded file %s", filename)
        self._bot_msg.edit_text(f"Download Complete", disable_web_page_preview=True)
        ext = filetype.guess_extension(file_path_obj)
        # Rename file if it doesn't have extension
        if ext is not None and not filename.endswith(ext):
            new_filename = f"{tempdir}/{filename}.{ext}"
            os.rename(file_path_obj, new_filename)
        # Get file path of the downloaded file to upload
        video_paths = list(pathlib.Path(tempdir).glob("*"))
        self._client.send_chat_action(chat_id, enums.ChatAction.UPLOAD_DOCUMENT)
        upload_processor(self._client, self._bot_msg, self._url, video_paths)
        self._bot_msg.edit_text("Download success!✅")

    def _download(self, formats):
        if ENABLE_ARIA2:
            return self._aria2_download()
        return self._requests_download()
