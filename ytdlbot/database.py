#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - database.py
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

from config import MYSQL_HOST, MYSQL_PASS, MYSQL_USER, REDIS


class Redis:
    def __init__(self):
        db = 1
        try:
            self.r = redis.StrictRedis(host=REDIS, db=db, decode_responses=True)
            self.r.ping()
        except Exception:
            logging.warning("Redis connection failed, using fake redis instead.")
            self.r = fakeredis.FakeStrictRedis(host=REDIS, db=db, decode_responses=True)

        db_banner = "=" * 20 + "DB data" + "=" * 20
        quota_banner = "=" * 20 + "Celery" + "=" * 20
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
        super().__init__()

    def __del__(self):
        self.r.close()

    def update_metrics(self, metrics: str):
        logging.info(f"Setting metrics: {metrics}")
        all_ = f"all_{metrics}"
        today = f"today_{metrics}"
        self.r.hincrby("metrics", all_)
        self.r.hincrby("metrics", today)

    @staticmethod
    def generate_table(header, all_data: list):
        table = BeautifulTable()
        for data in all_data:
            table.rows.append(data)
        table.columns.header = header
        table.rows.header = [str(i) for i in range(1, len(all_data) + 1)]
        return table

    def show_usage(self):
        db = MySQL()
        db.cur.execute("select user_id,payment_amount,old_user,token from payment")
        data = db.cur.fetchall()
        fd = []
        for item in data:
            fd.append([item[0], item[1], item[2], item[3]])
        db_text = self.generate_table(["ID", "pay amount", "old user", "token"], fd)

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

        worker_data = InfluxDB.get_worker_data()
        fd = []
        for item in worker_data["data"]:
            fd.append(
                [
                    item.get("hostname", 0),
                    item.get("status", 0),
                    item.get("active", 0),
                    item.get("processed", 0),
                    item.get("task-failed", 0),
                    item.get("task-succeeded", 0),
                    ",".join(str(i) for i in item.get("loadavg", [])),
                ]
            )

        worker_text = self.generate_table(
            ["worker name", "status", "active", "processed", "failed", "succeeded", "Load Average"], fd
        )

        # vnstat
        if os.uname().sysname == "Darwin":
            cmd = "/opt/homebrew/bin/vnstat -i en0".split()
        else:
            cmd = "/usr/bin/vnstat -i eth0".split()
        vnstat_text = subprocess.check_output(cmd).decode("u8")
        return self.final_text % (db_text, vnstat_text, worker_text, metrics_text, usage_text)

    def reset_today(self):
        pairs = self.r.hgetall("metrics")
        for k in pairs:
            if k.startswith("today"):
                self.r.hdel("metrics", k)

        self.r.delete("premium")

    def user_count(self, user_id):
        self.r.hincrby("metrics", user_id)

    def generate_file(self):
        text = self.show_usage()
        file = BytesIO()
        file.write(text.encode("u8"))
        date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
        file.name = f"{date}.txt"
        return file

    def add_send_cache(self, unique: str, file_id: str):
        self.r.hset("cache", unique, file_id)

    def get_send_cache(self, unique) -> str:
        return self.r.hget("cache", unique)

    def del_send_cache(self, unique):
        return self.r.hdel("cache", unique)


class MySQL:
    payment_sql = """
    CREATE TABLE if not exists `payment`
    (
        `user_id`        bigint NOT NULL,
        `payment_amount` float        DEFAULT NULL,
        `payment_id`     varchar(256) DEFAULT NULL,
        `old_user`       tinyint(1)   DEFAULT NULL,
        `token`          int          DEFAULT NULL,
        UNIQUE KEY `payment_id` (`payment_id`)
    ) CHARSET = utf8mb4
                """

    settings_sql = """
    create table if not exists  settings
    (
        user_id    bigint          not null,
        resolution varchar(128) null,
        method     varchar(64)  null,
        mode varchar(32) default 'Celery' null,
        history varchar(10) default 'OFF' null,
        constraint settings_pk
            primary key (user_id)
    );
            """

    channel_sql = """
    create table if not exists channel
    (
        link              varchar(256) null,
        title             varchar(256) null,
        description       text         null,
        channel_id        varchar(256),
        playlist          varchar(256) null,
        latest_video varchar(256) null,
        constraint channel_pk
            primary key (channel_id)
    ) CHARSET=utf8mb4;
    """

    subscribe_sql = """
    create table if not exists subscribe
    (
        user_id    bigint       null,
        channel_id varchar(256) null,
        is_valid boolean default 1 null
    ) CHARSET=utf8mb4;
    """
    history_sql = """
    create table if not exists history
    (
        user_id bigint null,
        link varchar(256) null,
        title varchar(512) null
    ) CHARSET=utf8mb4;
    """

    def __init__(self):
        self.con = pymysql.connect(host=MYSQL_HOST, user=MYSQL_USER, passwd=MYSQL_PASS, db="ytdl", charset="utf8mb4")

        self.con.ping(reconnect=True)
        self.cur = self.con.cursor()
        self.init_db()
        super().__init__()

    def init_db(self):
        self.cur.execute(self.payment_sql)
        self.cur.execute(self.settings_sql)
        self.cur.execute(self.channel_sql)
        self.cur.execute(self.subscribe_sql)
        self.cur.execute(self.history_sql)
        self.con.commit()

    def __del__(self):
        self.con.close()

    def get_user_settings(self, user_id: int) -> tuple:
        self.cur.execute("SELECT * FROM settings WHERE user_id = %s", (user_id,))
        data = self.cur.fetchone()
        if data is None:
            return 100, "high", "video", "Celery", "OFF"
        return data

    def set_user_settings(self, user_id: int, field: str, value: str):
        cur = self.con.cursor()
        cur.execute("SELECT * FROM settings WHERE user_id = %s", (user_id,))
        data = cur.fetchone()
        if data is None:
            resolution = method = ""
            if field == "resolution":
                method = "video"
                resolution = value
            if field == "method":
                method = value
                resolution = "high"
            cur.execute("INSERT INTO settings VALUES (%s,%s,%s,%s,%s)", (user_id, resolution, method, "Celery", "OFF"))
        else:
            cur.execute(f"UPDATE settings SET {field} =%s WHERE user_id = %s", (value, user_id))
        self.con.commit()

    def show_history(self, user_id: int):
        self.cur.execute("SELECT link,title FROM history WHERE user_id = %s", (user_id,))
        data = self.cur.fetchall()
        return "\n".join([f"{i[0]} {i[1]}" for i in data])

    def clear_history(self, user_id: int):
        self.cur.execute("DELETE FROM history WHERE user_id = %s", (user_id,))
        self.con.commit()

    def add_history(self, user_id: int, link: str, title: str):
        self.cur.execute("INSERT INTO history VALUES (%s,%s,%s)", (user_id, link, title))
        self.con.commit()

    def search_history(self, user_id: int, kw: str):
        self.cur.execute("SELECT * FROM history WHERE user_id = %s AND title like %s", (user_id, f"%{kw}%"))
        data = self.cur.fetchall()
        if data:
            return data
        return None
