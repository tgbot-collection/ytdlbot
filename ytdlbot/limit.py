#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - limit.py
# 8/15/21 18:23
#

__author__ = "Benny <benny.think@gmail.com>"

import hashlib
import logging
import time

import requests

from config import (
    AFD_TOKEN,
    AFD_USER_ID,
    COFFEE_TOKEN,
    EXPIRE,
    FREE_DOWNLOAD,
    OWNER,
    TOKEN_PRICE,
)
from database import MySQL, Redis
from utils import apply_log_formatter, current_time

apply_log_formatter()


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

    def _get_bmac_status(self, email: str) -> dict:
        self._get_data(self._url)
        for user in self._data:
            if user["payer_email"] == email or user["support_email"] == email:
                return user
        return {}

    def get_user_payment(self, email: str) -> (int, "float", str):
        order = self._get_bmac_status(email)
        price = float(order.get("support_coffee_price", 0))
        cups = float(order.get("support_coffees", 1))
        amount = price * cups
        return amount, email


class Afdian:
    def __init__(self):
        self._token = AFD_TOKEN
        self._user_id = AFD_USER_ID
        self._url = "https://afdian.net/api/open/query-order"

    def _generate_signature(self):
        data = {
            "user_id": self._user_id,
            "params": '{"x":0}',
            "ts": int(time.time()),
        }
        sign_text = "{token}params{params}ts{ts}user_id{user_id}".format(
            token=self._token, params=data["params"], ts=data["ts"], user_id=data["user_id"]
        )

        md5 = hashlib.md5(sign_text.encode("u8"))
        md5 = md5.hexdigest()
        data["sign"] = md5

        return data

    def _get_afdian_status(self, trade_no: str) -> dict:
        req_data = self._generate_signature()
        data = requests.post(self._url, json=req_data).json()
        # latest 50
        for order in data["data"]["list"]:
            if order["out_trade_no"] == trade_no:
                return order

        return {}

    def get_user_payment(self, trade_no: str) -> (int, float, str):
        order = self._get_afdian_status(trade_no)
        amount = float(order.get("show_amount", 0))
        # convert to USD
        return amount / 7, trade_no


class Payment(Redis, MySQL):
    def check_old_user(self, user_id: int) -> tuple:
        self.cur.execute("SELECT * FROM payment WHERE user_id=%s AND old_user=1", (user_id,))
        data = self.cur.fetchone()
        return data

    def get_pay_token(self, user_id: int) -> int:
        self.cur.execute("SELECT token, old_user FROM payment WHERE user_id=%s", (user_id,))
        data = self.cur.fetchall() or [(0, False)]
        number = sum([i[0] for i in data if i[0]])
        if number == 0 and data[0][1] != 1:
            # not old user, no token
            logging.warning("User %s has no token, set download mode to Celery", user_id)
            # change download mode to Celery
            self.set_user_settings(user_id, "mode", "Celery")
        return number

    def get_free_token(self, user_id: int) -> int:
        if self.r.exists(user_id):
            return int(self.r.get(user_id))
        else:
            # set and return
            self.r.set(user_id, FREE_DOWNLOAD, ex=EXPIRE)
            return FREE_DOWNLOAD

    def get_token(self, user_id: int):
        ttl = self.r.ttl(user_id)
        return self.get_free_token(user_id), self.get_pay_token(user_id), current_time(time.time() + ttl)

    def use_free_token(self, user_id: int):
        if self.r.exists(user_id):
            self.r.decr(user_id, 1)
        else:
            # first time download
            self.r.set(user_id, 5 - 1, ex=EXPIRE)

    def use_pay_token(self, user_id: int):
        # a user may pay multiple times, so we'll need to filter the first payment with valid token
        self.cur.execute("SELECT payment_id FROM payment WHERE user_id=%s AND token>0", (user_id,))
        data = self.cur.fetchone()
        payment_id = data[0]
        logging.info("User %s use pay token with payment_id %s", user_id, payment_id)
        self.cur.execute("UPDATE payment SET token=token-1 WHERE payment_id=%s", (payment_id,))
        self.con.commit()

    def use_token(self, user_id: int):
        free = self.get_free_token(user_id)
        if free > 0:
            self.use_free_token(user_id)
        else:
            self.use_pay_token(user_id)

    def add_pay_user(self, pay_data: list):
        self.cur.execute("INSERT INTO payment VALUES (%s,%s,%s,%s,%s)", pay_data)
        self.con.commit()

    def verify_payment(self, user_id: int, unique: str) -> str:
        pay = BuyMeACoffee() if "@" in unique else Afdian()
        self.cur.execute("SELECT * FROM payment WHERE payment_id=%s ", (unique,))
        data = self.cur.fetchone()
        if data:
            # TODO what if a user pay twice with the same email address?
            return (
                f"Failed. Payment has been verified by other users. Please contact @{OWNER} if you have any questions."
            )

        amount, pay_id = pay.get_user_payment(unique)
        logging.info("User %s paid %s, identifier is %s", user_id, amount, unique)
        # amount is already in USD
        if amount == 0:
            return "Payment not found. Please check your payment ID or email address"
        self.add_pay_user([user_id, amount, pay_id, 0, amount * TOKEN_PRICE])
        return "Thanks! Your payment has been verified. /start to get your token details"
