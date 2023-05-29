#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - constant.py
# 8/16/21 16:59
#

__author__ = "Benny <benny.think@gmail.com>"

import os

from config import (
    AFD_LINK,
    COFFEE_LINK,
    ENABLE_CELERY,
    FREE_DOWNLOAD,
    REQUIRED_MEMBERSHIP,
    TOKEN_PRICE,
)
from database import InfluxDB
from utils import get_func_queue


class BotText:
    start = "Welcome to YouTube Download bot. Type /help for more information."
    help = f"""
1. This bot should work at all times. If it doesn't, please wait for a few minutes and try sending the link again.

2. At the time of writing, this bot consumes more than 100GB of network traffic per day. 
To prevent abuse, each user is limited to 5 downloads per 24 hours.

3. You have the option to buy more tokens. Type /buy for more information.

4. The source code for this bot will always remain open and can be found here: https://github.com/tgbot-collection/ytdlbot

5. Need help with deployment or exclusive features? I offer paid service - contact me at @BennyThink
    """

    about = "YouTube Downloader by @BennyThink.\n\nOpen source on GitHub: https://github.com/tgbot-collection/ytdlbot"

    buy = f"""
**Terms:**
1. You can use this service free of charge for up to {FREE_DOWNLOAD} downloads within a 24-hour period, regardless of whether the download is successful or not.

2. You can purchase additional download tokens, which will be valid indefinitely.

3. I will not gather any personal information, so I won't know how many or which videos you have downloaded.

4. Refunds are possible, but you will be responsible for the processing fee charged by the payment provider (Stripe, Buy Me a Coffee, etc.).

5. I will record your unique ID after a successful payment, which is usually your payment ID or email address.

6. Paid user can change default download mode to Local mode in settings, which is faster. If your used up all your tokens, you will be reset to default mode.

**Download token price:**
1. Everyone: {FREE_DOWNLOAD} tokens per 24 hours, free of charge.
2. 1 USD == {TOKEN_PRICE} tokens, valid indefinitely.
3. 7 CNY == {TOKEN_PRICE} tokens, valid indefinitely.

**Payment option:**
1.  AFDIAN(AliPay, WeChat Pay and PayPal): {AFD_LINK}
2. Buy me a coffee: {COFFEE_LINK}
3. Telegram Payment(Stripe), see following invoice.

**After payment:**

1. Afdian: Provide your order number with the /redeem command (e.g., `/redeem 123456`).
2. Buy Me a Coffee: Provide your email with the /redeem command (e.g., `/redeem some@one.com`). **Use different email each time.**
3. Telegram Payment: Your payment will be automatically activated.

Want to buy more token at once? Let's say 100? Here you go! `/buy 123`
    """
    private = "This bot is for private use"
    membership_require = f"You need to join this group or channel to use this bot\n\nhttps://t.me/{REQUIRED_MEMBERSHIP}"

    settings = """
Please choose the desired format and video quality for your video. Note that these settings only **apply to YouTube videos**.

High quality is recommended. Medium quality is 720P, while low quality is 480P.

Please keep in mind that if you choose to send the video as a document, it will not be possible to stream it.

Your current settings:
Video quality: **{0}**
Sending format: **{1}**
"""
    custom_text = os.getenv("CUSTOM_TEXT", "")

    @staticmethod
    def get_receive_link_text() -> str:
        reserved = get_func_queue("reserved")
        if ENABLE_CELERY and reserved:
            text = f"Too many tasks. Your tasks was added to the reserved queue {reserved}."
        else:
            text = "Your task was added to active queue.\nProcessing...\n\n"

        return text

    @staticmethod
    def ping_worker() -> str:
        from tasks import app as celery_app

        workers = InfluxDB().extract_dashboard_data()
        # [{'celery@BennyのMBP': 'abc'}, {'celery@BennyのMBP': 'abc'}]
        response = celery_app.control.broadcast("ping_revision", reply=True)
        revision = {}
        for item in response:
            revision.update(item)

        text = ""
        for worker in workers:
            fields = worker["fields"]
            hostname = worker["tags"]["hostname"]
            status = {True: "✅"}.get(fields["status"], "❌")
            active = fields["active"]
            load = "{},{},{}".format(fields["load1"], fields["load5"], fields["load15"])
            rev = revision.get(hostname, "")
            text += f"{status}{hostname} **{active}** {load} {rev}\n"

        return text
