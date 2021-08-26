#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - constant.py
# 8/16/21 16:59
#

__author__ = "Benny <benny.think@gmail.com>"

import time

from downloader import sizeof_fmt
from limit import EX, MULTIPLY, QUOTA, USD2CNY, VIP


class BotText:
    start = "Welcome to YouTube Download bot. Type /help for more information."

    help = f"""
I'm sorry guys, the bot is consuming too many network traffic, so I addressed more strict limit.
If you have any troubles, you can talk to me and I'll see if I can ease the limitations for you.

1. This bot should works at all times. 
If it stops responding, please wait a few minutes or let me know on Telegram or GitHub.

2. At this time of writing, this bot consumes hundreds of GigaBytes of network traffic per day. 
In order to avoid being abused, 
every one can use this bot within {sizeof_fmt(QUOTA)} of quota for every {int(EX / 3600)} hours.

3. You can optionally choose to become 'VIP' user if you need more traffic. Type /vip for more information.

4. Sourcecode for this bot will always stay open, here-> https://github.com/tgbot-collection/ytdlbot
    """

    about = "YouTube-DL by @BennyThink. Open source on GitHub: https://github.com/tgbot-collection/ytdlbot"

    terms = f"""
1. You can use this service, free of charge, {sizeof_fmt(QUOTA)} per {int(EX / 3600)} hours.

2. The above traffic, is counted for one-way. 
For example, if you download a video of 1GB, your current quota will be 9GB instead of 8GB.

3. I won't gather any personal information, which means I don't know how many and what videos did you download.

4. Please try not to abuse this service.

5. It's a open source project, you can always deploy your own bot.

6. For VIPs, please refer to /vip command
    """

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
Note: If you pay $9, you'll become VIP1 instead of VIP2.

**Payment method:**
1. (afdian) Mainland China: https://afdian.net/@BennyThink
2. (buy me a coffee) Other countries or regions: https://www.buymeacoffee.com/bennythink
__I live in a place where I don't have access to Telegram Payments. So...__

**After payment:**
1. afdian: with your order number `/vip 123456`
2. buy me a coffee: with your email `/vip someone@else.com`
    """
    vip_pay = "Processing your payments...If it's not responding after one minute, please contact @BennyThink."

    def remaining_quota_caption(self, chat_id):
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
        v = VIP().check_vip(chat_id)
        if v:
            return f"Hello {v[1]}, VIP{v[-2]}☺️\n\n"
        else:
            return ""
