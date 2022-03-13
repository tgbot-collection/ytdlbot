#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - limit.py
# 8/15/21 18:23
#

__author__ = "Benny <benny.think@gmail.com>"

import hashlib
import http
import logging
import math
import os
import re
import time
from unittest.mock import MagicMock

import requests
from bs4 import BeautifulSoup

from config import (AFD_TOKEN, AFD_USER_ID, COFFEE_TOKEN, ENABLE_VIP, EX,
                    MULTIPLY, OWNER, QUOTA, USD2CNY)
from db import MySQL, Redis
from utils import apply_log_formatter

apply_log_formatter()


class VIP(Redis, MySQL):

    def check_vip(self, user_id: "int") -> "tuple":
        self.cur.execute("SELECT * FROM vip WHERE user_id=%s", (user_id,))
        data = self.cur.fetchone()
        return data

    def add_vip(self, user_data: "dict") -> ("bool", "str"):
        sql = "INSERT INTO vip VALUES (%s,%s,%s,%s,%s,%s);"
        # first select
        self.cur.execute("SELECT * FROM vip WHERE payment_id=%s", (user_data["payment_id"],))
        is_exist = self.cur.fetchone()
        if is_exist:
            return "Failed. {} is being used by user {}".format(user_data["payment_id"], is_exist[0])
        self.cur.execute(sql, list(user_data.values()))
        self.con.commit()
        # also remove redis cache
        self.r.delete(user_data["user_id"])
        return "Success! You are VIP{} now!".format(user_data["level"])

    def remove_vip(self, user_id: "int"):
        raise NotImplementedError()

    def get_user_quota(self, user_id: "int") -> int:
        # even VIP have certain quota
        q = self.check_vip(user_id)
        return q[-1] if q else QUOTA

    def check_remaining_quota(self, user_id: "int"):
        user_quota = self.get_user_quota(user_id)
        ttl = self.r.ttl(user_id)
        q = int(self.r.get(user_id)) if self.r.exists(user_id) else user_quota
        if q <= 0:
            q = 0
        return q, user_quota, ttl

    def use_quota(self, user_id: "int", traffic: "int"):
        user_quota = self.get_user_quota(user_id)
        # fix for standard mode
        if isinstance(user_quota, MagicMock):
            user_quota = 2 ** 32
        if self.r.exists(user_id):
            self.r.decr(user_id, traffic)
        else:
            self.r.set(user_id, user_quota - traffic, ex=EX)

    def subscribe_channel(self, user_id: "int", share_link: "str"):
        if not re.findall(r"youtube\.com|youtu\.be", share_link):
            raise ValueError("Is this a valid YouTube Channel link?")
        if ENABLE_VIP:
            self.cur.execute("select count(user_id) from subscribe where user_id=%s", (user_id,))
            usage = int(self.cur.fetchone()[0])
            if usage >= 5 and not self.check_vip(user_id):
                logging.warning("User %s is not VIP but has subscribed %s channels", user_id, usage)
                return "You have subscribed too many channels. Please upgrade to VIP to subscribe more channels."

        data = self.get_channel_info(share_link)
        channel_id = data["channel_id"]

        self.cur.execute("select user_id from subscribe where user_id=%s and channel_id=%s", (user_id, channel_id))
        if self.cur.fetchall():
            raise ValueError("You have already subscribed this channel.")

        self.cur.execute("INSERT IGNORE INTO channel values"
                         "(%(link)s,%(title)s,%(description)s,%(channel_id)s,%(playlist)s,%(last_video)s)", data)
        self.cur.execute("INSERT INTO subscribe values(%s,%s)", (user_id, channel_id))
        self.con.commit()
        logging.info("User %s subscribed channel %s", user_id, data["title"])
        return "Subscribed to {}".format(data["title"])

    def unsubscribe_channel(self, user_id: "int", channel_id: "str"):
        affected_rows = self.cur.execute("DELETE FROM subscribe WHERE user_id=%s AND channel_id=%s",
                                         (user_id, channel_id))
        self.con.commit()
        logging.info("User %s tried to unsubscribe channel %s", user_id, channel_id)
        return affected_rows

    @staticmethod
    def extract_canonical_link(url):
        # canonic link works for many websites. It will strip out unnecessary stuff
        proxy = {"https": os.getenv("YTDL_PROXY")} if os.getenv("YTDL_PROXY") else None
        props = ["canonical", "alternate", "shortlinkUrl"]
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36"}
        # send head request first
        r = requests.head(url, headers=headers, proxies=proxy)
        if r.status_code != http.HTTPStatus.METHOD_NOT_ALLOWED and "text/html" not in r.headers.get("content-type"):
            # get content-type, if it's not text/html, there's no need to issue a GET request
            logging.warning("%s Content-type is not text/html, no need to GET for extract_canonical_link", url)
            return url

        html_doc = requests.get(url, headers=headers, timeout=5, proxies=proxy).text
        soup = BeautifulSoup(html_doc, "html.parser")
        for prop in props:
            element = soup.find("link", rel=prop)
            try:
                href = element["href"]
                if href not in ["null", "", None]:
                    return href
            except Exception:
                logging.warning("Canonical exception %s", url)

        return url

    def get_channel_info(self, url: "str"):
        api_key = os.getenv("GOOGLE_API_KEY")
        canonical_link = self.extract_canonical_link(url)
        channel_id = canonical_link.split("https://www.youtube.com/channel/")[1]
        channel_api = f"https://www.googleapis.com/youtube/v3/channels?part=snippet,contentDetails&" \
                      f"id={channel_id}&key={api_key}"
        data = requests.get(channel_api).json()
        snippet = data['items'][0]['snippet']
        title = snippet['title']
        description = snippet['description']
        playlist = data['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        return {
            "link": url,
            "title": title,
            "description": description,
            "channel_id": channel_id,
            "playlist": playlist,
            "last_video": VIP.get_latest_video(playlist)
        }

    @staticmethod
    def get_latest_video(playlist_id: "str"):
        api_key = os.getenv("GOOGLE_API_KEY")
        video_api = f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&maxResults=1&" \
                    f"playlistId={playlist_id}&key={api_key}"
        data = requests.get(video_api).json()
        video_id = data['items'][0]['snippet']['resourceId']['videoId']
        logging.info(f"Latest video %s from %s", video_id, data['items'][0]['snippet']['channelTitle'])
        return f"https://www.youtube.com/watch?v={video_id}"

    def has_newer_update(self, channel_id: "str"):
        self.cur.execute("SELECT playlist,latest_video FROM channel WHERE channel_id=%s", (channel_id,))
        data = self.cur.fetchone()
        playlist_id = data[0]
        old_video = data[1]
        newest_video = VIP.get_latest_video(playlist_id)
        if old_video != newest_video:
            logging.info("Newer update found for %s %s", channel_id, newest_video)
            self.cur.execute("UPDATE channel SET latest_video=%s WHERE channel_id=%s", (newest_video, channel_id))
            self.con.commit()
            return newest_video

    def get_user_subscription(self, user_id: "int"):
        self.cur.execute(
            """
               select title, link, channel.channel_id from channel, subscribe 
               where subscribe.user_id = %s and channel.channel_id = subscribe.channel_id
            """, (user_id,))
        data = self.cur.fetchall()
        text = ""
        for item in data:
            text += "[{}]({}) `{}\n`".format(*item)
        return text

    def group_subscriber(self):
        # {"channel_id": [user_id, user_id, ...]}
        self.cur.execute("select * from subscribe where is_valid=1")
        data = self.cur.fetchall()
        group = {}
        for item in data:
            group.setdefault(item[1], []).append(item[0])
        logging.info("Checking periodic subscriber...")
        return group

    def deactivate_user_subscription(self, user_id: "int"):
        self.cur.execute("UPDATE subscribe set is_valid=0 WHERE user_id=%s", (user_id,))
        self.con.commit()

    def sub_count(self):
        sql = """
        select user_id, channel.title, channel.link
        from subscribe, channel where subscribe.channel_id = channel.channel_id
        """
        self.cur.execute(sql)
        data = self.cur.fetchall()
        text = f"Total {len(data)} subscriptions found.\n\n"
        for item in data:
            text += "{} ==> [{}]({})\n".format(*item)
        return text

    def del_cache(self, user_link: "str"):
        unique = self.extract_canonical_link(user_link)
        caches = self.r.hgetall("cache")
        count = 0
        for key in caches:
            if key.startswith(unique):
                count += self.del_send_cache(key)
        return count


class BuyMeACoffee:
    def __init__(self):
        self._token = COFFEE_TOKEN
        self._url = "https://developers.buymeacoffee.com/api/v1/supporters"
        self._data = []

    def _get_data(self, url):
        d = requests.get(url, headers={"Authorization": f"Bearer {self._token}"}).json()
        self._data.extend(d["data"])
        next_page = d["next_page_url"]
        if next_page:
            self._get_data(next_page)

    def _get_bmac_status(self, email: "str") -> "dict":
        self._get_data(self._url)
        for user in self._data:
            if user["payer_email"] == email or user["support_email"] == email:
                return user
        return {}

    def get_user_payment(self, email: "str") -> ("int", "float", "str"):
        order = self._get_bmac_status(email)
        price = float(order.get("support_coffee_price", 0))
        cups = float(order.get("support_coffees", 1))
        amount = price * cups
        level = math.floor(amount / MULTIPLY)
        return level, amount, email


class Afdian:
    def __init__(self):
        self._token = AFD_TOKEN
        self._user_id = AFD_USER_ID
        self._url = "https://afdian.net/api/open/query-order"

    def _generate_signature(self):
        data = {
            "user_id": self._user_id,
            "params": "{\"x\":0}",
            "ts": int(time.time()),
        }
        sign_text = "{token}params{params}ts{ts}user_id{user_id}".format(
            token=self._token, params=data['params'], ts=data["ts"], user_id=data["user_id"]
        )

        md5 = hashlib.md5(sign_text.encode("u8"))
        md5 = md5.hexdigest()
        data["sign"] = md5

        return data

    def _get_afdian_status(self, trade_no: "str") -> "dict":
        req_data = self._generate_signature()
        data = requests.post(self._url, json=req_data).json()
        # latest 50
        for order in data["data"]["list"]:
            if order["out_trade_no"] == trade_no:
                return order

        return {}

    def get_user_payment(self, trade_no: "str") -> ("int", "float", "str"):
        order = self._get_afdian_status(trade_no)
        amount = float(order.get("show_amount", 0))
        level = math.floor(amount / (MULTIPLY * USD2CNY))
        return level, amount, trade_no


def verify_payment(user_id, unique, client) -> "str":
    if not ENABLE_VIP:
        return "VIP is not enabled."
    logging.info("Verifying payment for %s - %s", user_id, unique)
    if "@" in unique:
        pay = BuyMeACoffee()
    else:
        pay = Afdian()

    level, amount, pay_id = pay.get_user_payment(unique)
    if amount == 0:
        return f"You pay amount is {amount}. Did you input wrong order ID or email? " \
               f"Talk to @{OWNER} if you need any assistant."
    if not level:
        return f"You pay amount {amount} is below minimum ${MULTIPLY}. " \
               f"Talk to @{OWNER} if you need any assistant."
    else:
        vip = VIP()
        ud = {
            "user_id": user_id,
            "username": client.get_chat(user_id).first_name,
            "payment_amount": amount,
            "payment_id": pay_id,
            "level": level,
            "quota": QUOTA * level * MULTIPLY
        }

        message = vip.add_vip(ud)
        return message


def subscribe_query():
    vip = VIP()
    for cid, uid in vip.group_subscriber().items():
        has = vip.has_newer_update(cid)
        if has:
            print(f"{has} - {uid}")
