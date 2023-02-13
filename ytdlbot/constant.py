#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - constant.py
# 8/16/21 16:59
#

__author__ = "Benny <benny.think@gmail.com>"

import os
import time

from config import (AFD_LINK, BURST, COFFEE_LINK, ENABLE_CELERY, ENABLE_VIP,
                    EX, MULTIPLY, RATE, REQUIRED_MEMBERSHIP, USD2CNY)
from db import InfluxDB
from downloader import sizeof_fmt
from limit import QUOTA, VIP
from utils import get_func_queue


class BotText:
    start = "Welcome to YouTube Download bot. Type /help for more information."

    help = f"""
1. This bot should works at all times. If it doesn't, wait for a few minutes, try to send the link again.

2. At this time of writing, this bot consumes more than 100GB of network traffic per day. 
In order to avoid being abused, 
every one can use this bot within **{sizeof_fmt(QUOTA)} of quota for every {int(EX / 3600)} hours.**

3. You can optionally choose to become 'VIP' user if you need more traffic. Type /vip for more information.

4. Source code for this bot will always stay open, here-> https://github.com/tgbot-collection/ytdlbot

5. Request limit is applied for everyone, excluding VIP users.
    """ if ENABLE_VIP else "Help text"

    about = "YouTube-DL by @BennyThink. Open source on GitHub: https://github.com/tgbot-collection/ytdlbot"

    vip = f"""
**Terms:**
1. You can use this service, free of charge, {sizeof_fmt(QUOTA)} per {int(EX / 3600)} hours.
2. The above traffic, is counted one-way. For example, if you download a video of 1GB, your will use 1GB instead of 2GB.
3. Streaming support is limited due to high costs of conversion.
4. I won't gather any personal information, which means I don't know how many and what videos did you download.
5. No rate limit for VIP users.
6. Possible to refund, but you'll have to bear with process fee. 
7. I'll record your unique ID after a successful payment, usually it's payment ID or email address.
8. VIP identity won't expire.
9. Please try not to abuse this service. It's a open source project, you can always deploy your own bot.

**Pay Tier:**
1. Everyone: {sizeof_fmt(QUOTA)} per {int(EX / 3600)} hours
2. VIP1: ${MULTIPLY} or ¥{MULTIPLY * USD2CNY}, {sizeof_fmt(QUOTA * 2)} per {int(EX / 3600)} hours
3. VIP2: ${MULTIPLY * 2} or ¥{MULTIPLY * USD2CNY * 2}, {sizeof_fmt(QUOTA * 2 * 2)} per {int(EX / 3600)} hours
4. VIP4....VIPn.

**Temporary top up**
Just want more traffic for a short period of time? Don't worry, you can use /topup command to top up your quota. 
It's valid permanently, until you use it up.

**Payment method:**
1. (afdian) Mainland China: {AFD_LINK}
2. (buy me a coffee) Other countries or regions: {COFFEE_LINK}
3. Telegram Payment(stripe), please directly using /tgvip command.

**After payment:**

1. afdian: with your order number `/vip 123456`
2. buy me a coffee: with your email `/vip someone@else.com`
3. Telegram Payment: automatically activated
    """ if ENABLE_VIP else "VIP is not enabled."
    vip_pay = "Processing your payments...If it's not responding after one minute, please contact @BennyThink."

    private = "This bot is for private use"
    membership_require = f"You need to join this group or channel to use this bot\n\nhttps://t.me/{REQUIRED_MEMBERSHIP}"

    settings = """
Select sending format and video quality. **Only applies to YouTube**
High quality is recommended; Medium quality is aimed as 720P while low quality is aimed as 480P.
    
Remember if you choose to send as document, there will be no streaming. 

Your current settings:
Video quality: **{0}**
Sending format: **{1}**
"""
    custom_text = os.getenv("CUSTOM_TEXT", "")
    topup_description = f"US$1 will give you {sizeof_fmt(QUOTA)} traffic permanently"
    topup_title = "Pay US$1 for more traffic!"

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

    too_fast = f"You have reached rate limit. Current rate limit is 1 request per {RATE} seconds, {BURST - 1} bursts."
