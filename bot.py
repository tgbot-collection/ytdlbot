#!/usr/local/bin/python3
# coding: utf-8

# ytdl-bot - bot.py
# 5/3/21 18:31
#

__author__ = "Benny <benny.think@gmail.com>"

import tempfile
import os
import logging
import threading
import asyncio
import traceback

import fakeredis
import youtube_dl
from telethon import TelegramClient, events
from tgbot_ping import get_runtime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(filename)s [%(levelname)s]: %(message)s')

token = os.getenv("TOKEN") or "17Zg"
app_id = int(os.getenv("APP_ID") or "922")
app_hash = os.getenv("APP_HASH") or "490"

bot = TelegramClient('bot', app_id, app_hash).start(bot_token=token)

r = fakeredis.FakeStrictRedis()

EXPIRE = 5


async def upload_callback(current, total, chat_id, message):
    key = f"{chat_id}-{message.id}"
    # if the key exists, we shouldn't send edit message
    if not r.exists(key):
        msg = f'Uploading {round(current / total * 100, 2)}%: {current}/{total}'
        await bot.edit_message(chat_id, message, msg)
        r.set(key, "ok", ex=EXPIRE)


async def sync_edit_message(chat_id, message, msg):
    # try to avoid flood
    key = f"{chat_id}-{message.id}"
    if not r.exists(key):
        await bot.edit_message(chat_id, message, msg)
        r.set(key, "ok", ex=EXPIRE)


def go(chat_id, message, msg):
    asyncio.run(sync_edit_message(chat_id, message, msg))


def progress_hook(d: dict, chat_id, message):
    if d['status'] == 'downloading':
        downloaded = d["downloaded_bytes"]
        total = d["total_bytes"]
        percent = d["_percent_str"]
        speed = d["_speed_str"]
        msg = f'Downloading {percent}: {downloaded}/{total} @ {speed}'
        threading.Thread(target=go, args=(chat_id, message, msg)).start()


async def ytdl_download(url, tempdir, chat_id, message) -> dict:
    response = dict(status=None, error=None, filepath=None)
    logging.info("Downloading for %s", url)
    output = os.path.join(tempdir, '%(title)s.%(ext)s')
    ydl_opts = {
        'progress_hooks': [lambda d: progress_hook(d, chat_id, message)],
        'outtmpl': output,
        'restrictfilenames': True
    }
    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        response["status"] = True
        response["filepath"] = os.path.join(tempdir, [i for i in os.listdir(tempdir)][0])
    except Exception:
        err = traceback.format_exc()
        logging.error("Download  failed for %s ", url)
        response["status"] = False
        response["error"] = err

    return response


@bot.on(events.NewMessage(pattern='/start'))
async def send_welcome(event):
    async with bot.action(event.chat_id, 'typing'):
        await bot.send_message(event.chat_id, "Wrapper for youtube-dl.")
        raise events.StopPropagation


@bot.on(events.NewMessage(pattern='/help'))
async def send_welcome(event):
    async with bot.action(event.chat_id, 'typing'):
        await bot.send_message(event.chat_id, "Bot is not working? "
                                              "Wait a few seconds, send your link again or report bugs at "
                                              "https://github.com/tgbot-collection/ytdl-bot/issues")
        raise events.StopPropagation


@bot.on(events.NewMessage(pattern='/ping'))
async def send_welcome(event):
    async with bot.action(event.chat_id, 'typing'):
        bot_info = get_runtime("botsrunner_ytdl_1", "YouTube-dl")
        await bot.send_message(event.chat_id, f"{bot_info}\n", parse_mode='md')
        raise events.StopPropagation


@bot.on(events.NewMessage(pattern='/about'))
async def send_welcome(event):
    async with bot.action(event.chat_id, 'typing'):
        await bot.send_message(event.chat_id, "YouTube-DL by @BennyThink\n"
                                              "GitHub: https://github.com/tgbot-collection/ytdl-bot")
        raise events.StopPropagation


@bot.on(events.NewMessage(incoming=True))
async def echo_all(event):
    chat_id = event.message.chat_id
    url = event.message.text
    message = await event.reply("Processing...")
    temp_dir = tempfile.TemporaryDirectory()

    async with bot.action(chat_id, 'video'):
        result = await ytdl_download(url, temp_dir.name, chat_id, message)

    if result["status"]:
        async with bot.action(chat_id, 'document'):
            video_path = result["filepath"]
            await bot.edit_message(chat_id, message, 'Download complete. Sending now...')
            await bot.send_file(chat_id, video_path,
                                progress_callback=lambda x, y: upload_callback(x, y, chat_id, message))
            await bot.edit_message(chat_id, message, 'Download success!✅')
    else:
        async with bot.action(chat_id, 'typing'):
            tb = result["error"]
            await bot.edit_message(chat_id, message, f"{url} download failed❌：\n```{tb}```",
                                   parse_mode='markdown')

    temp_dir.cleanup()


if __name__ == '__main__':
    bot.start()
    bot.run_until_disconnected()
