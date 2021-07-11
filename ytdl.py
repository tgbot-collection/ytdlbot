#!/usr/local/bin/python3
# coding: utf-8

# ytdl-bot - bot.py
# 5/3/21 18:31
#

__author__ = "Benny <benny.think@gmail.com>"

import asyncio
import datetime
import functools
import logging
import os
import platform
import re
import subprocess
import tempfile
import threading
import traceback

import fakeredis
import filetype
import youtube_dl
from hachoir.metadata import extractMetadata
from hachoir.metadata.audio import FlacMetadata
from hachoir.metadata.video import MkvMetadata
from hachoir.parser import createParser
from telethon import Button, TelegramClient, events
from telethon.tl.types import (DocumentAttributeAudio,
                               DocumentAttributeFilename,
                               DocumentAttributeVideo)
from telethon.utils import get_input_media
from tgbot_ping import get_runtime
from youtube_dl.utils import DownloadError

from FastTelethon import download_file, upload_file

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(filename)s [%(levelname)s]: %(message)s')
logging.getLogger('telethon').setLevel(logging.WARNING)

token = os.getenv("TOKEN") or "17Zg"
app_id = int(os.getenv("APP_ID") or "922")
app_hash = os.getenv("APP_HASH") or "490"

bot = TelegramClient('bot', app_id, app_hash,
                     device_model=f"{platform.system()} {platform.node()}-{os.path.basename(__file__)}",
                     system_version=platform.platform()).start(bot_token=token)

r = fakeredis.FakeStrictRedis()
EXPIRE = 5


def get_metadata(video_path):
    try:
        metadata = extractMetadata(createParser(video_path))
        if isinstance(metadata, MkvMetadata):
            return dict(
                duration=metadata.get('duration').seconds,
                w=metadata['video[1]'].get('width'),
                h=metadata['video[1]'].get('height')
            ), metadata.get('mime_type')
        elif isinstance(metadata, FlacMetadata):
            return dict(
                duration=metadata.get('duration').seconds,
            ), metadata.get('mime_type')
        else:
            return dict(
                duration=metadata.get('duration').seconds,
                w=metadata.get('width'),
                h=metadata.get('height')
            ), metadata.get('mime_type')
    except Exception as e:
        logging.error(e)
        return dict(duration=0, w=0, h=0), 'application/octet-stream'


def go(chat_id, message, msg):
    asyncio.run(sync_edit_message(chat_id, message, msg))


def sizeof_fmt(num: int, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def progress_hook(d: dict, chat_id, message):
    if d['status'] == 'downloading':
        downloaded = d.get("downloaded_bytes", 0)
        total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
        filesize = sizeof_fmt(total)
        if total > 2 * 1024 * 1024 * 1024:
            raise Exception("\n\nYour video is too large. %s will exceed Telegram's max limit 2GiB" % filesize)

        percent = d.get("_percent_str", "N/A")
        speed = d.get("_speed_str", "N/A")
        msg = f'[{filesize}]: Downloading {percent} - {downloaded}/{total} @ {speed}'
        threading.Thread(target=go, args=(chat_id, message, msg)).start()


def run_in_executor(f):
    @functools.wraps(f)
    def inner(*args, **kwargs):
        loop = asyncio.get_running_loop()
        return loop.run_in_executor(None, lambda: f(*args, **kwargs))

    return inner


@run_in_executor
def ytdl_download(url, tempdir, chat_id, message) -> dict:
    response = dict(status=None, error=None, filepath=None)
    logging.info("Downloading for %s", url)
    output = os.path.join(tempdir, '%(title)s.%(ext)s')
    ydl_opts = {
        'progress_hooks': [lambda d: progress_hook(d, chat_id, message)],
        'outtmpl': output,
        'restrictfilenames': True,
        'quiet': True
    }
    formats = [
        "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio",
        "bestvideo[vcodec^=avc]+bestaudio[acodec^=mp4a]/best[vcodec^=avc]/best",
        ""
    ]
    success, err = None, None
    for f in formats:
        if f:
            ydl_opts["format"] = f
        try:
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            success = True
        except DownloadError:
            err = traceback.format_exc()
            logging.error("Download failed for %s ", url)

        if success:
            response["status"] = True
            response["filepath"] = os.path.join(tempdir, [i for i in os.listdir(tempdir)][0])
            break
        else:
            response["status"] = False
            response["error"] = err
    # convert format if necessary
    convert_to_mp4(response)
    return response


def convert_to_mp4(resp: dict):
    default_type = ["video/x-flv"]
    if resp["status"]:
        mime = filetype.guess(resp["filepath"]).mime
        if mime in default_type:
            path = resp["filepath"]
            new_name = os.path.basename(path).split(".")[0] + ".mp4"
            new_file_path = os.path.join(os.path.dirname(path), new_name)
            cmd = "ffmpeg -i {} {}".format(path, new_file_path)
            logging.info("Detected %s, converting to mp4...", mime)
            subprocess.check_output(cmd.split())
            resp["filepath"] = new_file_path
            return resp


async def upload_callback(current, total, chat_id, message):
    key = f"{chat_id}-{message.id}"
    # if the key exists, we shouldn't send edit message
    if not r.exists(key):
        r.set(key, "ok", ex=EXPIRE)
        filesize = sizeof_fmt(total)
        msg = f'[{filesize}]: Uploading {round(current / total * 100, 2)}% - {current}/{total}'
        await bot.edit_message(chat_id, message, msg)


async def sync_edit_message(chat_id, message, msg):
    # try to avoid flood
    key = f"{chat_id}-{message.id}"
    if not r.exists(key):
        r.set(key, "ok", ex=EXPIRE)
        await bot.edit_message(chat_id, message, msg)


# bot starts here
@bot.on(events.NewMessage(pattern='/start'))
async def send_start(event):
    logging.info("Welcome to youtube-dl bot!")
    async with bot.action(event.chat_id, 'typing'):
        await bot.send_message(event.chat_id, "Wrapper for youtube-dl.")
        raise events.StopPropagation


import pathlib


async def convert_flac(flac_name, tmp):
    flac_tmp = pathlib.Path(tmp.name).parent.joinpath(flac_name).as_posix()
    cmd = "ffmpeg -y -i {} {}".format(tmp.name, flac_tmp)
    logging.info("converting to flac")
    subprocess.check_output(cmd.split())
    return flac_tmp


@bot.on(events.CallbackQuery)
async def handler(event):
    await event.answer('Converting to audio...please wait patiently')
    msg = await event.get_message()
    chat_id = msg.chat_id
    mp4_name = msg.file.name  # 'youtube-dl_test_video_a.mp4'
    flac_name = mp4_name.replace("mp4", "flac")

    with tempfile.NamedTemporaryFile() as tmp:
        with open(tmp.name, "wb") as out:
            logging.info("downloading to %s", tmp.name)
            async with bot.action(chat_id, 'record-round'):
                await download_file(event.client, msg.media.document, out, )
            logging.info("downloading complete %s", tmp.name)
        # execute ffmpeg
        async with bot.action(chat_id, 'record-audio'):
            await asyncio.sleep(1)
            flac_tmp = await convert_flac(flac_name, tmp)
        async with bot.action(chat_id, 'document'):
            logging.info("Converting flac complete, sending...")
            with open(flac_tmp, 'rb') as f:
                input_file = await upload_file(bot, f)
                metadata, mime_type = get_metadata(flac_tmp)
                input_media = get_input_media(input_file)
                input_media.attributes = [
                    DocumentAttributeAudio(duration=metadata["duration"]),
                    DocumentAttributeFilename(flac_name),
                ]
                input_media.mime_type = mime_type
                await bot.send_file(chat_id, input_media)

            # await bot.send_file(chat_id, flac_tmp)

    tmp.close()


@bot.on(events.NewMessage(pattern='/help'))
async def send_help(event):
    async with bot.action(event.chat_id, 'typing'):
        await bot.send_message(event.chat_id, "Bot is not working? "
                                              "Wait a few seconds, send your link again or report bugs at "
                                              "https://github.com/tgbot-collection/ytdl-bot/issues")
        raise events.StopPropagation


@bot.on(events.NewMessage(pattern='/ping'))
async def send_ping(event):
    async with bot.action(event.chat_id, 'typing'):
        bot_info = get_runtime("botsrunner_ytdl_1", "YouTube-dl")
        await bot.send_message(event.chat_id, f"{bot_info}\n", parse_mode='md')
        raise events.StopPropagation


@bot.on(events.NewMessage(pattern='/about'))
async def send_about(event):
    async with bot.action(event.chat_id, 'typing'):
        await bot.send_message(event.chat_id, "YouTube-DL by @BennyThink\n"
                                              "GitHub: https://github.com/tgbot-collection/ytdl-bot")
        raise events.StopPropagation


@bot.on(events.NewMessage(incoming=True))
async def send_video(event):
    chat_id = event.message.chat_id
    url = re.sub(r'/ytdl\s*', '', event.message.text)
    logging.info("start %s", url)
    # if this is in a group/channel
    if not event.message.is_private and not event.message.text.lower().startswith("/ytdl"):
        logging.warning("%s, it's annoying me...🙄️ ", event.message.text)
        return
    if not re.findall(r"^https?://", url.lower()):
        await event.reply("I think you should send me a link. Don't you agree with me?")
        return

    message = await event.reply("Processing...")
    temp_dir = tempfile.TemporaryDirectory()

    async with bot.action(chat_id, 'video'):
        result = await ytdl_download(url, temp_dir.name, chat_id, message)

    # markup
    markup = bot.build_reply_markup(Button.inline('flac'))
    if result["status"]:
        async with bot.action(chat_id, 'document'):
            video_path = result["filepath"]
            await bot.edit_message(chat_id, message, 'Download complete. Sending now...')
            metadata, mime_type = get_metadata(video_path)
            with open(video_path, 'rb') as f:
                input_file = await upload_file(
                    bot, f,
                    progress_callback=lambda x, y: upload_callback(x, y, chat_id, message))
            input_media = get_input_media(input_file)
            file_name = os.path.basename(video_path)
            input_media.attributes = [
                DocumentAttributeVideo(round_message=False, supports_streaming=True, **metadata),
                DocumentAttributeFilename(file_name),
            ]
            input_media.mime_type = mime_type
            # duration here is int - convert to timedelta
            metadata["duration_str"] = datetime.timedelta(seconds=metadata["duration"])
            metadata["size"] = sizeof_fmt(os.stat(video_path).st_size)
            caption = "{name}\n{duration_str} {size} {w}*{h}".format(name=file_name, **metadata)
            await bot.send_file(chat_id, input_media, caption=caption, buttons=markup)
            await bot.edit_message(chat_id, message, 'Download success!✅')
    else:
        async with bot.action(chat_id, 'typing'):
            tb = result["error"][0:4000]
            await bot.edit_message(chat_id, message, f"{url} download failed❌：\n```{tb}```",
                                   parse_mode='markdown')

    temp_dir.cleanup()


if __name__ == '__main__':
    bot.run_until_disconnected()
