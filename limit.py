#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - limit.py
# 8/15/21 18:23
#

__author__ = "Benny <benny.think@gmail.com>"

import json
import os
import sqlite3
import typing

import redis

QUOTA = 10 * 1024 * 1024 * 1024  # 10G
EX = 24 * 3600
MULTIPLY = 5  # VIP1 is 5*10-50G, VIP2 is 100G


class Redis:
    def __init__(self):
        self.r = redis.StrictRedis(host=os.getenv("redis") or "localhost", decode_responses=True)

    def __del__(self):
        self.r.close()


class SQLite(Redis):
    def __init__(self):
        super(SQLite, self).__init__()
        self.con = sqlite3.connect("vip.sqlite", check_same_thread=False)
        self.cur = self.con.cursor()
        SQL = """
            create table if not exists VIP
            (
                user_id    integer 
                    constraint VIP
                        primary key,
                username   varchar(100),
                payment    integer,
                payment_id varchar(100),
                level     integer default 1,
                quota int default %s
            );
        """ % QUOTA
        self.cur.execute(SQL)

    def __del__(self):
        super(SQLite, self).__del__()
        self.con.close()


class VIP(SQLite):

    def check_vip(self, user_id: "int") -> "tuple":
        self.cur.execute("SELECT * FROM VIP WHERE user_id=?", (user_id,))
        data = self.cur.fetchone()
        return data

    def add_vip(self, user_data: "dict"):
        user_data["quota"] = QUOTA * user_data["level"] * MULTIPLY
        sql = "INSERT INTO VIP VALUES (?,?,?,?,?,?);"
        self.cur.execute(sql, list(user_data.values()))
        self.con.commit()

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
            self.r.set(user_id, user_quota, ex=EX)


if __name__ == '__main__':
    vip = VIP()
    ud = {"user_id": 260260121, "username": "bahd", "payment": 5, "payment_id": "dhja767", "level": 1}
    vip.add_vip(ud)
    # print(vip.check_remaining_quota("12345"))
    # vip.use_quota(12345, 1 * 1024 * 1024 * 1024)
    # print(vip.check_remaining_quota(12345))
