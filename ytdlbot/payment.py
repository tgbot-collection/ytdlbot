#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - payment.py
# 8/15/21 18:23
#

__author__ = "Benny <benny.think@gmail.com>"

import logging
import time

from tronpy import Tron
from tronpy.exceptions import TransactionError, ValidationError
from tronpy.hdwallet import key_from_seed, seed_from_mnemonic
from tronpy.keys import PrivateKey
from tronpy.providers import HTTPProvider

from config import (
    EXPIRE,
    FREE_DOWNLOAD,
    OWNER,
    TOKEN_PRICE,
    TRON_MNEMONIC,
    TRONGRID_KEY,
    TRX_SIGNAL,
)
from database import MySQL, Redis
from utils import apply_log_formatter, current_time

apply_log_formatter()


class TronTrx:
    def __init__(self):
        if TRON_MNEMONIC == "cram floor today legend service drill pitch leaf car govern harvest soda":
            logging.warning("Using nile testnet")
            provider = HTTPProvider(endpoint_uri="https://nile.trongrid.io")
            network = "nile"
        else:
            provider = HTTPProvider(api_key=TRONGRID_KEY)
            network = "mainnet"
        self.client = Tron(provider, network=network)

    def central_transfer(self, from_, index, amount: int):
        logging.info("Generated key with index %s", index)
        seed = seed_from_mnemonic(TRON_MNEMONIC, passphrase="")
        key = PrivateKey(key_from_seed(seed, account_path=f"m/44'/195'/1'/0/{index}"))
        central = self.central_wallet()
        logging.info("Transfer %s TRX from %s to %s", amount, from_, central)
        try:
            self.client.trx.transfer(from_, central, amount).build().sign(key).broadcast()
        except (TransactionError, ValidationError):
            logging.error("Failed to transfer %s TRX to %s. Lower and try again.", amount, from_)
            if amount > 1_100_000:
                # 1.1 trx transfer fee
                self.client.trx.transfer(from_, central, amount - 1_100_000).build().sign(key).broadcast()

    def central_wallet(self):
        wallet = self.client.generate_address_from_mnemonic(TRON_MNEMONIC, account_path="m/44'/195'/0'/0/0")
        return wallet["base58check_address"]

    def get_payment_address(self, user_id):
        # payment_id is like tron,0,TN8Mn9KKv3cSrKyrt6Xx5L18nmezbpiW31,index where 0 means unpaid
        db = MySQL()
        con = db.con
        cur = db.cur
        cur.execute("select user_id from payment where payment_id like 'tron,%'")
        data = cur.fetchall()
        index = len(data)
        path = f"m/44'/195'/1'/0/{index}"
        logging.info("Generating address for user %s with path %s", user_id, path)
        addr = self.client.generate_address_from_mnemonic(TRON_MNEMONIC, account_path=path)["base58check_address"]
        # add row in db, unpaid
        cur.execute("insert into payment values (%s,%s,%s,%s,%s)", (user_id, 0, f"tron,0,{addr},{index}", 0, 0))
        con.commit()
        return addr

    def check_payment(self):
        db = MySQL()
        con = db.con
        cur = db.cur

        cur.execute("select user_id, payment_id from payment where payment_id like 'tron,0,T%'")
        data = cur.fetchall()
        for row in data:
            logging.info("Checking user payment %s", row)
            user_id = row[0]
            addr, index = row[1].split(",")[2:]
            try:
                balance = self.client.get_account_balance(addr)
            except:
                balance = 0
            if balance:
                logging.info("User %s has %s TRX", user_id, balance)
                # paid, calc token count
                token_count = int(balance / 10 * TOKEN_PRICE)
                cur.execute(
                    "update payment set token=%s,payment_id=%s where user_id=%s and payment_id like %s",
                    (token_count, f"tron,1,{addr},{index}", user_id, f"tron,%{addr}%"),
                )
                cur.execute("UPDATE settings SET mode='Local' WHERE user_id=%s", (user_id,))
                con.commit()
                self.central_transfer(addr, index, int(balance * 1_000_000))
                logging.debug("Dispatch signal now....")
                TRX_SIGNAL.send("cron", user_id=user_id, text=f"{balance} TRX received, {token_count} tokens added.")


class Payment(Redis, MySQL):

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
        self.set_user_settings(pay_data[0], "mode", "Local")
        self.con.commit()

    def verify_payment(self, user_id: int, unique: str) -> str:
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


if __name__ == "__main__":
    a = TronTrx()
    # a.central_wallet()
    a.check_payment()
