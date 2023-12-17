#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - new.py
# 8/14/21 14:37
#

__author__ = "Benny <benny.think@gmail.com>"

import contextlib
import logging
import os
import random
import re
import tempfile
import time
import traceback
from io import BytesIO
from typing import Any

import pyrogram.errors
import qrcode
import yt_dlp
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client, enums, filters, types
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant
from pyrogram.raw import functions
from pyrogram.raw import types as raw_types
from tgbot_ping import get_runtime
from youtubesearchpython import VideosSearch

from channel import Channel
from client_init import create_app
from config import (
    AUTHORIZED_USER,
    ENABLE_CELERY,
    ENABLE_FFMPEG,
    ENABLE_VIP,
    IS_BACKUP_BOT,
    M3U8_SUPPORT,
    OWNER,
    PLAYLIST_SUPPORT,
    PROVIDER_TOKEN,
    REQUIRED_MEMBERSHIP,
    TOKEN_PRICE,
    TRX_SIGNAL,
)
from constant import BotText
from database import InfluxDB, MySQL, Redis
from limit import Payment, TronTrx
from tasks import app as celery_app
from tasks import (
    audio_entrance,
    direct_download_entrance,
    hot_patch,
    purge_tasks,
    ytdl_download_entrance,
)
from utils import auto_restart, clean_tempfile, customize_logger, get_revision

logging.info("Authorized users are %s", AUTHORIZED_USER)
customize_logger(["pyrogram.client", "pyrogram.session.session", "pyrogram.connection.connection"])
logging.getLogger("apscheduler.executors.default").propagate = False

app = create_app("main")
channel = Channel()


def private_use(func):
    def wrapper(client: Client, message: types.Message):
        chat_id = getattr(message.from_user, "id", None)

        # message type check
        if message.chat.type != enums.ChatType.PRIVATE and not message.text.lower().startswith("/ytdl"):
            logging.debug("%s, it's annoying me...🙄️ ", message.text)
            return

        # authorized users check
        if AUTHORIZED_USER:
            users = [int(i) for i in AUTHORIZED_USER.split(",")]
        else:
            users = []

        if users and chat_id and chat_id not in users:
            message.reply_text(BotText.private, quote=True)
            return

        if REQUIRED_MEMBERSHIP:
            try:
                member: types.ChatMember | Any = app.get_chat_member(REQUIRED_MEMBERSHIP, chat_id)
                if member.status not in [
                    enums.ChatMemberStatus.ADMINISTRATOR,
                    enums.ChatMemberStatus.MEMBER,
                    enums.ChatMemberStatus.OWNER,
                ]:
                    raise UserNotParticipant()
                else:
                    logging.info("user %s check passed for group/channel %s.", chat_id, REQUIRED_MEMBERSHIP)
            except UserNotParticipant:
                logging.warning("user %s is not a member of group/channel %s", chat_id, REQUIRED_MEMBERSHIP)
                message.reply_text(BotText.membership_require, quote=True)
                return

        return func(client, message)

    return wrapper


@app.on_message(filters.command(["start"]))
def start_handler(client: Client, message: types.Message):
    payment = Payment()
    from_id = message.from_user.id
    logging.info("%s welcome to youtube-dl bot!", message.from_user.id)
    client.send_chat_action(from_id, enums.ChatAction.TYPING)
    is_old_user = payment.check_old_user(from_id)
    if is_old_user:
        info = ""
    if ENABLE_VIP:
        free_token, pay_token, reset = payment.get_token(from_id)
        info = f"Free token: {free_token}, Pay token: {pay_token}, Reset: {reset}"
    else:
        info = ""
    text = f"{BotText.start}\n\n{info}\n{BotText.custom_text}"
    client.send_message(message.chat.id, text, disable_web_page_preview=True)


@app.on_message(filters.command(["help"]))
def help_handler(client: Client, message: types.Message):
    chat_id = message.chat.id
    client.send_chat_action(chat_id, enums.ChatAction.TYPING)
    client.send_message(chat_id, BotText.help, disable_web_page_preview=True)


@app.on_message(filters.command(["about"]))
def about_handler(client: Client, message: types.Message):
    chat_id = message.chat.id
    client.send_chat_action(chat_id, enums.ChatAction.TYPING)
    client.send_message(chat_id, BotText.about)


@app.on_message(filters.command(["sub"]))
def subscribe_handler(client: Client, message: types.Message):
    chat_id = message.chat.id
    client.send_chat_action(chat_id, enums.ChatAction.TYPING)
    if message.text == "/sub":
        result = channel.get_user_subscription(chat_id)
    else:
        link = message.text.split()[1]
        try:
            result = channel.subscribe_channel(chat_id, link)
        except (IndexError, ValueError):
            result = f"Error: \n{traceback.format_exc()}"
    client.send_message(chat_id, result or "You have no subscription.", disable_web_page_preview=True)


@app.on_message(filters.command(["unsub"]))
def unsubscribe_handler(client: Client, message: types.Message):
    chat_id = message.chat.id
    client.send_chat_action(chat_id, enums.ChatAction.TYPING)
    text = message.text.split(" ")
    if len(text) == 1:
        client.send_message(chat_id, "/unsub channel_id", disable_web_page_preview=True)
        return

    rows = channel.unsubscribe_channel(chat_id, text[1])
    if rows:
        text = f"Unsubscribed from {text[1]}"
    else:
        text = "Unable to find the channel."
    client.send_message(chat_id, text, disable_web_page_preview=True)


@app.on_message(filters.command(["patch"]))
def patch_handler(client: Client, message: types.Message):
    username = message.from_user.username
    chat_id = message.chat.id
    if username == OWNER:
        celery_app.control.broadcast("hot_patch")
        client.send_chat_action(chat_id, enums.ChatAction.TYPING)
        client.send_message(chat_id, "Oorah!")
        hot_patch()


@app.on_message(filters.command(["uncache"]))
def uncache_handler(client: Client, message: types.Message):
    username = message.from_user.username
    link = message.text.split()[1]
    if username == OWNER:
        count = channel.del_cache(link)
        message.reply_text(f"{count} cache(s) deleted.", quote=True)


@app.on_message(filters.command(["purge"]))
def purge_handler(client: Client, message: types.Message):
    username = message.from_user.username
    if username == OWNER:
        message.reply_text(purge_tasks(), quote=True)


@app.on_message(filters.command(["ping"]))
def ping_handler(client: Client, message: types.Message):
    redis = Redis()
    chat_id = message.chat.id
    client.send_chat_action(chat_id, enums.ChatAction.TYPING)
    if os.uname().sysname == "Darwin" or ".heroku" in os.getenv("PYTHONHOME", ""):
        bot_info = "ping unavailable."
    else:
        bot_info = get_runtime("ytdlbot_ytdl_1", "YouTube-dl")
    if message.chat.username == OWNER:
        stats = BotText.ping_worker()[:1000]
        client.send_document(chat_id, redis.generate_file(), caption=f"{bot_info}\n\n{stats}")
    else:
        client.send_message(chat_id, f"{bot_info.split('CPU')[0]}")


@app.on_message(filters.command(["sub_count"]))
def sub_count_handler(client: Client, message: types.Message):
    username = message.from_user.username
    chat_id = message.chat.id
    if username == OWNER:
        with BytesIO() as f:
            f.write(channel.sub_count().encode("u8"))
            f.name = "subscription count.txt"
            client.send_document(chat_id, f)


@app.on_message(filters.command(["direct"]))
def direct_handler(client: Client, message: types.Message):
    redis = Redis()
    chat_id = message.from_user.id
    client.send_chat_action(chat_id, enums.ChatAction.TYPING)
    url = re.sub(r"/direct\s*", "", message.text)
    logging.info("direct start %s", url)
    if not re.findall(r"^https?://", url.lower()):
        redis.update_metrics("bad_request")
        message.reply_text("Send me a DIRECT LINK.", quote=True)
        return

    bot_msg = message.reply_text("Request received.", quote=True)
    redis.update_metrics("direct_request")
    direct_download_entrance(client, bot_msg, url)


@app.on_message(filters.command(["settings"]))
def settings_handler(client: Client, message: types.Message):
    chat_id = message.chat.id
    payment = Payment()
    client.send_chat_action(chat_id, enums.ChatAction.TYPING)
    data = MySQL().get_user_settings(chat_id)
    set_mode = data[-1]
    text = {"Local": "Celery", "Celery": "Local"}.get(set_mode, "Local")
    mode_text = f"Download mode: **{set_mode}**"
    if message.chat.username == OWNER or payment.get_pay_token(chat_id):
        extra = [types.InlineKeyboardButton(f"Change download mode to {text}", callback_data=text)]
    else:
        extra = []

    markup = types.InlineKeyboardMarkup(
        [
            [  # First row
                types.InlineKeyboardButton("send as document", callback_data="document"),
                types.InlineKeyboardButton("send as video", callback_data="video"),
                types.InlineKeyboardButton("send as audio", callback_data="audio"),
            ],
            [  # second row
                types.InlineKeyboardButton("High Quality", callback_data="high"),
                types.InlineKeyboardButton("Medium Quality", callback_data="medium"),
                types.InlineKeyboardButton("Low Quality", callback_data="low"),
            ],
            extra,
        ]
    )

    try:
        client.send_message(chat_id, BotText.settings.format(data[1], data[2]) + mode_text, reply_markup=markup)
    except:
        client.send_message(
            chat_id, BotText.settings.format(data[1] + ".", data[2] + ".") + mode_text, reply_markup=markup
        )


@app.on_message(filters.command(["buy"]))
def buy_handler(client: Client, message: types.Message):
    # process as chat.id, not from_user.id
    chat_id = message.chat.id
    client.send_chat_action(chat_id, enums.ChatAction.TYPING)
    # currency USD
    token_count = message.text.replace("/buy", "").strip()
    if token_count.isdigit():
        price = int(int(token_count) / TOKEN_PRICE * 100)
    else:
        price = 100

    markup = types.InlineKeyboardMarkup(
        [
            [
                types.InlineKeyboardButton("Bot Payments", callback_data=f"bot-payments-{price}"),
                types.InlineKeyboardButton("TRON(TRX)", callback_data="tron-trx"),
            ],
        ]
    )
    client.send_message(chat_id, BotText.buy, disable_web_page_preview=True, reply_markup=markup)


@app.on_callback_query(filters.regex(r"tron-trx"))
def tronpayment_btn_calback(client: Client, callback_query: types.CallbackQuery):
    callback_query.answer("Generating QR code...")
    chat_id = callback_query.message.chat.id
    client.send_chat_action(chat_id, enums.ChatAction.TYPING)

    addr = TronTrx().get_payment_address(chat_id)
    with BytesIO() as bio:
        qr = qrcode.make(addr)
        qr.save(bio)
        client.send_photo(chat_id, bio, caption=f"Send any amount of TRX to `{addr}`")


@app.on_callback_query(filters.regex(r"bot-payments-.*"))
def bot_payment_btn_calback(client: Client, callback_query: types.CallbackQuery):
    callback_query.answer("Generating invoice...")
    chat_id = callback_query.message.chat.id
    client.send_chat_action(chat_id, enums.ChatAction.TYPING)

    data = callback_query.data
    price = int(data.split("-")[-1])
    payload = f"{chat_id}-buy"
    invoice = generate_invoice(price, f"Buy {TOKEN_PRICE} download tokens", "Pay by card", payload)
    app.invoke(
        functions.messages.SendMedia(
            peer=(raw_types.InputPeerUser(user_id=chat_id, access_hash=0)),
            media=invoice,
            random_id=app.rnd_id(),
            message="Buy more download token",
        )
    )


@app.on_message(filters.command(["redeem"]))
def redeem_handler(client: Client, message: types.Message):
    payment = Payment()
    chat_id = message.chat.id
    text = message.text.strip()
    unique = text.replace("/redeem", "").strip()
    msg = payment.verify_payment(chat_id, unique)
    message.reply_text(msg, quote=True)


def generate_invoice(amount: int, title: str, description: str, payload: str):
    invoice = raw_types.input_media_invoice.InputMediaInvoice(
        invoice=raw_types.invoice.Invoice(
            currency="USD", prices=[raw_types.LabeledPrice(label="price", amount=amount)]
        ),
        title=title,
        description=description,
        provider=PROVIDER_TOKEN,
        provider_data=raw_types.DataJSON(data="{}"),
        payload=payload.encode(),
        start_param=payload,
    )
    return invoice


def link_checker(url: str) -> str:
    if url.startswith("https://www.instagram.com"):
        return ""
    ytdl = yt_dlp.YoutubeDL()

    if not PLAYLIST_SUPPORT and (
        re.findall(r"^https://www\.youtube\.com/channel/", Channel.extract_canonical_link(url)) or "list" in url
    ):
        return "Playlist or channel links are disabled."

    if not M3U8_SUPPORT and (re.findall(r"m3u8|\.m3u8|\.m3u$", url.lower())):
        return "m3u8 links are disabled."

    with contextlib.suppress(yt_dlp.utils.DownloadError):
        if ytdl.extract_info(url, download=False).get("live_status") == "is_live":
            return "Live stream links are disabled. Please download it after the stream ends."


def search_ytb(kw: str):
    videos_search = VideosSearch(kw, limit=10)
    text = ""
    results = videos_search.result()["result"]
    for item in results:
        title = item.get("title")
        link = item.get("link")
        index = results.index(item) + 1
        text += f"{index}. {title}\n{link}\n\n"
    return text


@app.on_message(filters.incoming & (filters.text | filters.document))
@private_use
def download_handler(client: Client, message: types.Message):
    redis = Redis()
    payment = Payment()
    chat_id = message.from_user.id
    client.send_chat_action(chat_id, enums.ChatAction.TYPING)
    redis.user_count(chat_id)
    if message.document:
        with tempfile.NamedTemporaryFile(mode="r+") as tf:
            logging.info("Downloading file to %s", tf.name)
            message.download(tf.name)
            contents = open(tf.name, "r").read()  # don't know why
        urls = contents.split()
    else:
        urls = [re.sub(r"/ytdl\s*", "", message.text)]
        logging.info("start %s", urls)

    for url in urls:
        # check url
        if not re.findall(r"^https?://", url.lower()):
            redis.update_metrics("bad_request")
            text = search_ytb(url)
            message.reply_text(text, quote=True, disable_web_page_preview=True)
            return

        if text := link_checker(url):
            message.reply_text(text, quote=True)
            redis.update_metrics("reject_link_checker")
            return

        # old user is not limited by token
        if ENABLE_VIP and not payment.check_old_user(chat_id):
            free, pay, reset = payment.get_token(chat_id)
            if free + pay <= 0:
                message.reply_text(f"You don't have enough token. Please wait until {reset} or /buy .", quote=True)
                redis.update_metrics("reject_token")
                return
            else:
                payment.use_token(chat_id)

        redis.update_metrics("video_request")

        text = BotText.get_receive_link_text()
        try:
            # raise pyrogram.errors.exceptions.FloodWait(10)
            bot_msg: types.Message | Any = message.reply_text(text, quote=True)
        except pyrogram.errors.Flood as e:
            f = BytesIO()
            f.write(str(e).encode())
            f.write(b"Your job will be done soon. Just wait! Don't rush.")
            f.name = "Please don't flood me.txt"
            bot_msg = message.reply_document(
                f, caption=f"Flood wait! Please wait {e} seconds...." f"Your job will start automatically", quote=True
            )
            f.close()
            client.send_message(OWNER, f"Flood wait! 🙁 {e} seconds....")
            time.sleep(e.value)

        client.send_chat_action(chat_id, enums.ChatAction.UPLOAD_VIDEO)
        bot_msg.chat = message.chat
        ytdl_download_entrance(client, bot_msg, url)


@app.on_callback_query(filters.regex(r"document|video|audio"))
def send_method_callback(client: Client, callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    data = callback_query.data
    logging.info("Setting %s file type to %s", chat_id, data)
    MySQL().set_user_settings(chat_id, "method", data)
    callback_query.answer(f"Your send type was set to {callback_query.data}")


@app.on_callback_query(filters.regex(r"high|medium|low"))
def download_resolution_callback(client: Client, callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    data = callback_query.data
    logging.info("Setting %s file type to %s", chat_id, data)
    MySQL().set_user_settings(chat_id, "resolution", data)
    callback_query.answer(f"Your default download quality was set to {callback_query.data}")


@app.on_callback_query(filters.regex(r"convert"))
def audio_callback(client: Client, callback_query: types.CallbackQuery):
    redis = Redis()
    if not ENABLE_FFMPEG:
        callback_query.answer("Request rejected.")
        callback_query.message.reply_text("Audio conversion is disabled now.")
        return

    callback_query.answer(f"Converting to audio...please wait patiently")
    redis.update_metrics("audio_request")
    audio_entrance(client, callback_query.message)


@app.on_callback_query(filters.regex(r"Local|Celery"))
def owner_local_callback(client: Client, callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    MySQL().set_user_settings(chat_id, "mode", callback_query.data)
    callback_query.answer(f"Download mode was changed to {callback_query.data}")


def periodic_sub_check():
    exceptions = pyrogram.errors.exceptions
    for cid, uids in channel.group_subscriber().items():
        video_url = channel.has_newer_update(cid)
        if video_url:
            logging.info(f"periodic update:{video_url} - {uids}")
            for uid in uids:
                try:
                    app.send_message(uid, f"{video_url} is out. Watch it on YouTube")
                except (exceptions.bad_request_400.PeerIdInvalid, exceptions.bad_request_400.UserIsBlocked) as e:
                    logging.warning("User is blocked or deleted. %s", e)
                    channel.deactivate_user_subscription(uid)
                except Exception:
                    logging.error("Unknown error when sending message to user. %s", traceback.format_exc())
                finally:
                    time.sleep(random.random() * 3)


@app.on_raw_update()
def raw_update(client: Client, update, users, chats):
    payment = Payment()
    action = getattr(getattr(update, "message", None), "action", None)
    if update.QUALNAME == "types.UpdateBotPrecheckoutQuery":
        client.invoke(
            functions.messages.SetBotPrecheckoutResults(
                query_id=update.query_id,
                success=True,
            )
        )
    elif action and action.QUALNAME == "types.MessageActionPaymentSentMe":
        logging.info("Payment received. %s", action)
        uid = update.message.peer_id.user_id
        amount = action.total_amount / 100
        payment.add_pay_user([uid, amount, action.charge.provider_charge_id, 0, amount * TOKEN_PRICE])
        client.send_message(uid, f"Thank you {uid}. Payment received: {amount} {action.currency}")


def trx_notify(_, **kwargs):
    user_id = kwargs.get("user_id")
    text = kwargs.get("text")
    logging.info("Sending trx notification to %s", user_id)
    app.send_message(user_id, text)


if __name__ == "__main__":
    MySQL()
    TRX_SIGNAL.connect(trx_notify)
    scheduler = BackgroundScheduler(timezone="Europe/London", job_defaults={"max_instances": 6})
    scheduler.add_job(auto_restart, "interval", seconds=600)
    scheduler.add_job(clean_tempfile, "interval", seconds=120)
    if not IS_BACKUP_BOT:
        scheduler.add_job(Redis().reset_today, "cron", hour=0, minute=0)
        scheduler.add_job(InfluxDB().collect_data, "interval", seconds=120)
        scheduler.add_job(TronTrx().check_payment, "interval", seconds=60, max_instances=1)
        #  default quota allocation of 10,000 units per day
        scheduler.add_job(periodic_sub_check, "interval", seconds=3600)
    scheduler.start()
    banner = f"""
▌ ▌         ▀▛▘     ▌       ▛▀▖              ▜            ▌
▝▞  ▞▀▖ ▌ ▌  ▌  ▌ ▌ ▛▀▖ ▞▀▖ ▌ ▌ ▞▀▖ ▌  ▌ ▛▀▖ ▐  ▞▀▖ ▝▀▖ ▞▀▌
 ▌  ▌ ▌ ▌ ▌  ▌  ▌ ▌ ▌ ▌ ▛▀  ▌ ▌ ▌ ▌ ▐▐▐  ▌ ▌ ▐  ▌ ▌ ▞▀▌ ▌ ▌
 ▘  ▝▀  ▝▀▘  ▘  ▝▀▘ ▀▀  ▝▀▘ ▀▀  ▝▀   ▘▘  ▘ ▘  ▘ ▝▀  ▝▀▘ ▝▀▘

By @BennyThink, VIP mode: {ENABLE_VIP}, Celery Mode: {ENABLE_CELERY}
Version: {get_revision()}
    """
    print(banner)
    app.run()
