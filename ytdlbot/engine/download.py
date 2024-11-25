#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - downloader.py
# 8/14/21 16:53
#

__author__ = "Benny <benny.think@gmail.com>"

import logging
import os
import pathlib
import re
import subprocess
import tempfile
import time
import traceback

import filetype
from pyrogram import types


def ytdl_download_entrance(client: Client, bot_msg: types.Message, url: str, mode=None):
    # in Local node and forward mode, we pass client from main
    # in celery mode, we need to use our own client called bot

    cached_fid = redis.get_send_cache(unique)

    try:
        if cached_fid:
            forward_video(client, bot_msg, url, cached_fid)
            return
        mode = mode or payment.get_user_settings(chat_id)[3]
        ytdl_normal_download(client, bot_msg, url)
    except FileTooBig as e:
        logging.warning("Seeking for help from premium user...")
        # this is only for normal node. Celery node will need to do it in celery tasks
        markup = premium_button(chat_id)
        if markup:
            bot_msg.edit_text(f"{e}\n\n{bot_text.premium_warning}", reply_markup=markup)
        else:
            bot_msg.edit_text(f"{e}\nBig file engine is not available now. Please /buy or try again later ")
    except Exception as e:
        logging.error("Failed to engine %s, error: %s", url, e)
        error_msg = traceback.format_exc().split("yt_dlp.utils.DownloadError: ERROR: ")
        if len(error_msg) > 1:
            bot_msg.edit_text(f"Download failed!❌\n\n`{error_msg[-1]}", disable_web_page_preview=True)
        else:
            bot_msg.edit_text(
                f"Download failed!❌\n\n`{traceback.format_exc()[-2000:]}`", disable_web_page_preview=True
            )


def spdl_download_entrance(client: Client, bot_msg: types.Message, url: str, mode=None):
    payment = Payment()
    redis = Redis()
    chat_id = bot_msg.chat.id
    unique = get_unique_clink(url, chat_id)
    cached_fid = redis.get_send_cache(unique)

    try:
        if cached_fid:
            forward_video(client, bot_msg, url, cached_fid)
            return
        mode = mode or payment.get_user_settings(chat_id)[3]
        spdl_normal_download(client, bot_msg, url)
    except FileTooBig as e:
        logging.warning("Seeking for help from premium user...")
        # this is only for normal node. Celery node will need to do it in celery tasks
        markup = premium_button(chat_id)
        if markup:
            bot_msg.edit_text(f"{e}\n\n{bot_text.premium_warning}", reply_markup=markup)
        else:
            bot_msg.edit_text(f"{e}\nBig file engine is not available now. Please /buy or try again later ")
    except ValueError as e:
        logging.error("Invalid URL provided: %s", e)
        bot_msg.edit_text(f"Download failed!❌\n\n{e}", disable_web_page_preview=True)
    except Exception as e:
        logging.error("Failed to engine %s, error: %s", url, e)
        error_msg = "Sorry, Something went wrong."
        bot_msg.edit_text(f"Download failed!❌\n\n`{error_msg}", disable_web_page_preview=True)


def leech_download_entrance(client: Client, bot_msg: typing.Union[types.Message, typing.Coroutine], url: str):
    chat_id = bot_msg.chat.id
    temp_dir = tempfile.TemporaryDirectory(prefix="leech_dl-", dir=TMPFILE_PATH)
    tempdir = temp_dir.name
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    response = None
    video_paths = None
    # Download process using aria2c
    try:
        bot_msg.edit_text(f"Download Starting...", disable_web_page_preview=True)
        # Command to engine the link using aria2c
        command = [
            "aria2c",
            "-U",
            UA,
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


def audio_entrance(client: Client, bot_msg: typing.Union[types.Message, typing.Coroutine]):
    chat_id = bot_msg.chat.id
    # fn = getattr(bot_msg.video, "file_name", None) or getattr(bot_msg.document, "file_name", None)
    status_msg: typing.Union[types.Message, typing.Coroutine] = bot_msg.reply_text(
        "Converting to audio...please wait patiently", quote=True
    )
    orig_url: str = re.findall(r"https?://.*", bot_msg.caption)[0]
    with tempfile.TemporaryDirectory(prefix="ytdl-", dir=TMPFILE_PATH) as tmp:
        client.send_chat_action(chat_id, enums.ChatAction.RECORD_AUDIO)
        # just try to engine the audio using yt-dlp
        filepath = ytdl_download(orig_url, tmp, status_msg, hijack="bestaudio[ext=m4a]")
        status_msg.edit_text("Sending audio now...")
        client.send_chat_action(chat_id, enums.ChatAction.UPLOAD_AUDIO)
        for f in filepath:
            client.send_audio(chat_id, f)
        status_msg.edit_text("✅ Conversion complete.")


def spdl_normal_download(client: Client, bot_msg: types.Message | typing.Any, url: str):
    chat_id = bot_msg.chat.id
    temp_dir = tempfile.TemporaryDirectory(prefix="spdl-", dir=TMPFILE_PATH)

    video_paths = sp_dl(url, temp_dir.name, bot_msg)
    logging.info("Download complete.")
    client.send_chat_action(chat_id, enums.ChatAction.UPLOAD_DOCUMENT)
    bot_msg.edit_text("Download complete. Sending now...")
    data = MySQL().get_user_settings(chat_id)
    if data[4] == "ON":
        logging.info("Adding to history...")
        MySQL().add_history(chat_id, url, pathlib.Path(video_paths[0]).name)
    try:
        upload_processor(client, bot_msg, url, video_paths)
    except pyrogram.errors.Flood as e:
        logging.critical("FloodWait from Telegram: %s", e)
        client.send_message(
            chat_id,
            f"I'm being rate limited by Telegram. Your video will come after {e} seconds. Please wait patiently.",
        )
        client.send_message(OWNER, f"CRITICAL INFO: {e}")
        time.sleep(e.value)
        upload_processor(client, bot_msg, url, video_paths)

    bot_msg.edit_text("Download success!✅")

    if RCLONE_PATH:
        for item in os.listdir(temp_dir.name):
            logging.info("Copying %s to %s", item, RCLONE_PATH)
            shutil.copy(os.path.join(temp_dir.name, item), RCLONE_PATH)
    temp_dir.cleanup()
