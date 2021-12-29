#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - db.py
# 12/7/21 16:57
#

__author__ = "Benny <benny.think@gmail.com>"

import logging
import os
import re
import subprocess
import time
from io import BytesIO

import fakeredis
import pymysql
import redis
from beautifultable import BeautifulTable

from config import MYSQL_HOST, MYSQL_PASS, MYSQL_USER, QUOTA, REDIS


class Redis:
    def __init__(self):
        super(Redis, self).__init__()
        if REDIS is None:
            self.r = fakeredis.FakeStrictRedis(host=REDIS, db=4, decode_responses=True)
        else:
            self.r = redis.StrictRedis(host=REDIS, db=4, decode_responses=True)

        db_banner = "=" * 20 + "DB data" + "=" * 20
        quota_banner = "=" * 20 + "Quota" + "=" * 20
        metrics_banner = "=" * 20 + "Metrics" + "=" * 20
        usage_banner = "=" * 20 + "Usage" + "=" * 20
        vnstat_banner = "=" * 20 + "vnstat" + "=" * 20
        self.final_text = f"""
{db_banner}
%s


{vnstat_banner}
%s


{quota_banner}
%s


{metrics_banner}
%s


{usage_banner}
%s
        """

    def __del__(self):
        self.r.close()

    def update_metrics(self, metrics):
        logging.info(f"Setting metrics: {metrics}")
        all_ = f"all_{metrics}"
        today = f"today_{metrics}"
        self.r.hincrby("metrics", all_)
        self.r.hincrby("metrics", today)

    def generate_table(self, header, all_data: "list"):
        table = BeautifulTable()
        for data in all_data:
            table.rows.append(data)
        table.columns.header = header
        table.rows.header = [str(i) for i in range(1, len(all_data) + 1)]
        return table

    def show_usage(self):
        from downloader import sizeof_fmt
        db = MySQL()
        db.cur.execute("select * from VIP")
        data = db.cur.fetchall()
        fd = []
        for item in data:
            fd.append([item[0], item[1], sizeof_fmt(item[-1])])
        db_text = self.generate_table(["ID", "username", "quota"], fd)

        fd = []
        hash_keys = self.r.hgetall("metrics")
        for key, value in hash_keys.items():
            if re.findall(r"^today|all", key):
                fd.append([key, value])
        fd.sort(key=lambda x: x[0])
        metrics_text = self.generate_table(["name", "count"], fd)

        fd = []
        for key, value in hash_keys.items():
            if re.findall(r"\d+", key):
                fd.append([key, value])
        fd.sort(key=lambda x: int(x[-1]), reverse=True)
        usage_text = self.generate_table(["UserID", "count"], fd)

        fd = []
        for key in self.r.keys("*"):
            if re.findall(r"\d+", key):
                value = self.r.get(key)
                date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.r.ttl(key) + time.time()))
                fd.append([key, value, sizeof_fmt(int(value)), date])
        fd.sort(key=lambda x: int(x[1]))
        quota_text = self.generate_table(["UserID", "bytes", "human readable", "refresh time"], fd)

        # vnstat
        if os.uname().sysname == "Darwin":
            cmd = "/usr/local/bin/vnstat -i en0".split()
        else:
            cmd = "/usr/bin/vnstat -i eth0".split()
        vnstat_text = subprocess.check_output(cmd).decode('u8')
        return self.final_text % (db_text, vnstat_text, quota_text, metrics_text, usage_text)

    def reset_today(self):
        pairs = self.r.hgetall("metrics")
        for k in pairs:
            if k.startswith("today"):
                self.r.hdel("metrics", k)

    def user_count(self, user_id):
        self.r.hincrby("metrics", user_id)

    def generate_file(self):
        text = self.show_usage()
        file = BytesIO()
        file.write(text.encode("u8"))
        date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
        file.name = f"{date}.txt"
        return file


class MySQL:
    vip_sql = """
    create table if not exists VIP
    (
        user_id        bigint             not null,
        username       varchar(256)    null,
        payment_amount int             null,
        payment_id     varchar(256)    null,
        level          int default 1   null,
        quota          bigint default %s null,
        constraint VIP_pk
            primary key (user_id)
    );
            """ % QUOTA

    settings_sql = """
    create table if not exists  settings
    (
        user_id    bigint          not null,
        resolution varchar(128) null,
        method     varchar(64)  null,
        constraint settings_pk
            primary key (user_id)
    );
            """

    def __init__(self):
        self.con = pymysql.connect(host=MYSQL_HOST, user=MYSQL_USER, passwd=MYSQL_PASS, db="vip", charset="utf8mb4")
        self.cur = self.con.cursor()
        self.init_db()

    def init_db(self):
        self.cur.execute(self.vip_sql)
        self.cur.execute(self.settings_sql)
        self.con.commit()

    def __del__(self):
        self.con.close()


if __name__ == '__main__':
    db = MySQL()
