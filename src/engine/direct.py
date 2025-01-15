#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - leech.py

import logging
import os
import pathlib
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

import filetype
import requests
from base import BaseDownloader
from pyrogram import enums

from config import ENABLE_ARIA2, TMPFILE_PATH


class DirectDownloader(BaseDownloader):

    def _setup_formats(self) -> list | None:
        # direct download doesn't need to setup formats
        pass

    def _requests_download(self):
        response = requests.get(self._url, stream=True)
        response.raise_for_status()
        file = Path(self._tempdir).joinpath(uuid4().hex)
        ext = filetype.guess_extension(file)
        if ext is not None:
            file = file.with_suffix(ext)

        with open(file, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return [file.as_posix()]

    def _aria2_download(self):
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        response = None
        video_paths = None
        # Download process using aria2c
        try:
            self._bot_msg.edit_text(f"Aria2 download starting...")
            # Command to engine the link using aria2c
            command = [
                "aria2c",
                "-U",
                ua,
                "--max-tries=5",
                "--console-log-level=warn",
                "-d",
                self._tempdir,
                self._url,
            ]
            # Run the command using subprocess.Popen
            process = subprocess.Popen(command, bufsize=0, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            max_iterations = 100  # Set a reasonable maximum number of iterations
            iteration = 0
            while process.poll() is None and iteration < max_iterations:
                line: str = process.stdout.readline().decode("utf-8")
                if line.startswith("[#"):
                    line = line.strip()
                    self.edit_text(f"Aria2 downloading... \n\n`{line}`", disable_web_page_preview=True)
                    break
                iteration += 1

            if iteration >= max_iterations:
                self.edit_text("Download exceed max iteration. Please try again later.", disable_web_page_preview=True)
        except Exception as e:
            self.edit_text(f"Download failed!❌\n\n`{e}`", disable_web_page_preview=True)
            return
        # Get filename and extension correctly after engine
        file: Path = next(Path(self._tempdir).glob("*"))
        filename = file.name
        logging.info("Downloaded file %s", filename)
        self.edit_text(f"Download Complete", disable_web_page_preview=True)
        ext = filetype.guess_extension(file)
        # Rename file if it doesn't have extension
        if ext is not None and not filename.endswith(ext):
            file.rename(f"{self._tempdir}/{filename}.{ext}")
        # Get file path of the downloaded file to upload
        return [file.as_posix()]

    def _download(self, formats=None) -> list:
        if ENABLE_ARIA2:
            return self._aria2_download()
        return self._requests_download()

    def _start(self):
        self._download()
        self._upload()
