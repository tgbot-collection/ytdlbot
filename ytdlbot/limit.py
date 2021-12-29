#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - limit.py
# 8/15/21 18:23
#

__author__ = "Benny <benny.think@gmail.com>"

import hashlib
import logging
import math
import tempfile
import time

import requests

from config import (AFD_TOKEN, AFD_USER_ID, COFFEE_TOKEN, ENABLE_VIP, EX,
                    MULTIPLY, OWNER, QUOTA, USD2CNY)
from db import MySQL, Redis
from utils import apply_log_formatter

apply_log_formatter()


def get_username(chat_id):
    from ytdl_bot import create_app
    with tempfile.NamedTemporaryFile() as tmp:
        with create_app(tmp.name, 1) as app:
            data = app.get_chat(chat_id).first_name

    return data


class VIP(Redis, MySQL):

    def check_vip(self, user_id: "int") -> "tuple":
        self.cur.execute("SELECT * FROM VIP WHERE user_id=%s", (user_id,))
        data = self.cur.fetchone()
        return data

    def add_vip(self, user_data: "dict") -> ("bool", "str"):
        sql = "INSERT INTO VIP VALUES (%s,%s,%s,%s,%s,%s);"
        # first select
        self.cur.execute("SELECT * FROM VIP WHERE payment_id=%s", (user_data["payment_id"],))
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
        if self.r.exists(user_id):
            self.r.decr(user_id, traffic)
        else:
            self.r.set(user_id, user_quota - traffic, ex=EX)


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


def verify_payment(user_id, unique) -> "str":
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
            "username": get_username(user_id),
            "payment_amount": amount,
            "payment_id": pay_id,
            "level": level,
            "quota": QUOTA * level * MULTIPLY
        }

        message = vip.add_vip(ud)
        return message


if __name__ == '__main__':
    res = Redis().generate_file()
    print(res.getvalue().decode())
