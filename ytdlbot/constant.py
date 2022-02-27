#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - constant.py
# 8/16/21 16:59
#

__author__ = "Benny <benny.think@gmail.com>"

import os
import time

from config import (AFD_LINK, COFFEE_LINK, ENABLE_CELERY, ENABLE_VIP, EX,
                    MULTIPLY, REQUIRED_MEMBERSHIP, USD2CNY)
from db import InfluxDB
from downloader import sizeof_fmt
from limit import QUOTA, VIP
from utils import get_func_queue


class BotText:
    start = "Welcome to YouTube Download bot. Type /help for more information."

    help = f"""
1. This bot should works at all times. If it doesn't, try to send the link again or DM @BennyThink

2. At this time of writing, this bot consumes hundreds of GigaBytes of network traffic per day. 
In order to avoid being abused, 
every one can use this bot within **{sizeof_fmt(QUOTA)} of quota for every {int(EX / 3600)} hours.**

3. Free users can't receive streaming formats of one video whose duration is longer than 300 seconds.

4. You can optionally choose to become 'VIP' user if you need more traffic. Type /vip for more information.

5. Source code for this bot will always stay open, here-> https://github.com/tgbot-collection/ytdlbot
    """ if ENABLE_VIP else "Help text"

    about = "YouTube-DL by @BennyThink. Open source on GitHub: https://github.com/tgbot-collection/ytdlbot"

    terms = f"""
1. You can use this service, free of charge, {sizeof_fmt(QUOTA)} per {int(EX / 3600)} hours.

2. The above traffic, is counted for one-way. 
For example, if you download a video of 1GB, your current quota will be 9GB instead of 8GB.

3. Streaming support is limited due to high costs of conversion.

4. I won't gather any personal information, which means I don't know how many and what videos did you download.

5. Please try not to abuse this service.

6. It's a open source project, you can always deploy your own bot.

7. For VIPs, please refer to /vip command
    """ if ENABLE_VIP else "Please contact the actual owner of this bot"

    vip = f"""
**Terms:**
1. No refund, I'll keep it running as long as I can.
2. I'll record your unique ID after a successful payment, usually it's payment ID or email address.
3. VIPs identity won't expire.

**Pay Tier:**
1. Everyone: {sizeof_fmt(QUOTA)} per {int(EX / 3600)} hours
2. VIP1: ${MULTIPLY} or ¥{MULTIPLY * USD2CNY}, {sizeof_fmt(QUOTA * 5)} per {int(EX / 3600)} hours
3. VIP2: ${MULTIPLY * 2} or ¥{MULTIPLY * USD2CNY * 2}, {sizeof_fmt(QUOTA * 5 * 2)} per {int(EX / 3600)} hours
4. VIP4....VIPn.
5. Unlimited streaming conversion support.
Note: If you pay $9, you'll become VIP1 instead of VIP2.

**Payment method:**
1. (afdian) Mainland China: {AFD_LINK}
2. (buy me a coffee) Other countries or regions: {COFFEE_LINK}
__I live in a place where I don't have access to Telegram Payments. So...__

**After payment:**
1. afdian: with your order number `/vip 123456`
2. buy me a coffee: with your email `/vip someone@else.com`
    """ if ENABLE_VIP else "VIP is not enabled."
    vip_pay = "Processing your payments...If it's not responding after one minute, please contact @BennyThink."

    private = "This bot is for private use"
    membership_require = f"You need to join this group or channel to use this bot\n\nhttps://t.me/{REQUIRED_MEMBERSHIP}"

    settings = """
Select sending format and video quality. **Only applies to YouTube**
High quality is recommended; Medium quality is aimed as 480P while low quality is aimed as 360P and 240P.
    
Remember if you choose to send as document, there will be no streaming. 

Your current settings:
Video quality: **{0}**
Sending format: **{1}**
"""
    custom_text = os.getenv("CUSTOM_TEXT", "")

    def remaining_quota_caption(self, chat_id):
        if not ENABLE_VIP:
            return ""
        used, total, ttl = self.return_remaining_quota(chat_id)
        refresh_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ttl + time.time()))
        caption = f"Remaining quota: **{sizeof_fmt(used)}/{sizeof_fmt(total)}**, " \
                  f"refresh at {refresh_time}\n"
        return caption

    @staticmethod
    def return_remaining_quota(chat_id):
        used, total, ttl = VIP().check_remaining_quota(chat_id)
        return used, total, ttl

    @staticmethod
    def get_vip_greeting(chat_id):
        if not ENABLE_VIP:
            return ""
        v = VIP().check_vip(chat_id)
        if v:
            return f"Hello {v[1]}, VIP{v[-2]}☺️\n\n"
        else:
            return ""

    @staticmethod
    def get_receive_link_text():
        reserved = get_func_queue("reserved")
        if ENABLE_CELERY and reserved:
            text = f"Too many tasks. Your tasks was added to the reserved queue {reserved}."
        else:
            text = "Your task was added to active queue.\nProcessing...\n\n"

        return text

    @staticmethod
    def ping_worker():
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
