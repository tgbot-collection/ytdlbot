#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - leech.py

import logging
import os
import pathlib
import subprocess
import tempfile

import filetype
from pyrogram import enums

from config import ENABLE_ARIA2, TMPFILE_PATH, Types
from upload import upload_processor


def direct_download_entrance():
    if ENABLE_ARIA2:
        return aria2_download
    return requests_download


def requests_download():
    pass


def aria2_download(client: Types.Client, bot_msg: Types.Message, url: str):
    chat_id = bot_msg.chat.id
    temp_dir = tempfile.TemporaryDirectory(prefix="ytdl-aria2-", dir=TMPFILE_PATH)
    tempdir = temp_dir.name
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    response = None
    video_paths = None
    # Download process using aria2c
    try:
        bot_msg.edit_text(f"Download Starting...", disable_web_page_preview=True)
        # Command to engine the link using aria2c
        command = [
            "aria2c",
            "-U",
            ua,
            "--max-tries=5",
            "--console-log-level=warn",
            "-d",
            tempdir,
            url,
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
                bot_msg.edit_text(f"Downloading... \n\n`{line}`", disable_web_page_preview=True)
                break
            iteration += 1

        if iteration >= max_iterations:
            bot_msg.edit_text("Something went wrong. Please try again.", disable_web_page_preview=True)
    except Exception as e:
        bot_msg.edit_text(f"Download failed!❌\n\n`{e}`", disable_web_page_preview=True)
        return
    # Get filename and extension correctly after engine
    filepath = list(pathlib.Path(tempdir).glob("*"))
    file_path_obj = filepath[0]
    path_obj = pathlib.Path(file_path_obj)
    filename = path_obj.name
    logging.info("Downloaded file %s", filename)
    bot_msg.edit_text(f"Download Complete", disable_web_page_preview=True)
    ext = filetype.guess_extension(file_path_obj)
    # Rename file if it doesn't have extension
    if ext is not None and not filename.endswith(ext):
        new_filename = f"{tempdir}/{filename}.{ext}"
        os.rename(file_path_obj, new_filename)
    # Get file path of the downloaded file to upload
    video_paths = list(pathlib.Path(tempdir).glob("*"))
    client.send_chat_action(chat_id, enums.ChatAction.UPLOAD_DOCUMENT)
    upload_processor(client, bot_msg, url, video_paths)
    bot_msg.edit_text("Download success!✅")
