#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - fakemysql.py
# 2/20/22 20:08
#

__author__ = "Benny <benny.think@gmail.com>"

import re
import sqlite3

init_con = sqlite3.connect(":memory:", check_same_thread=False)


class FakeMySQL:
    @staticmethod
    def cursor() -> "Cursor":
        return Cursor()

    def commit(self):
        pass

    def close(self):
        pass


class Cursor:
    def __init__(self):
        self.con = init_con
        self.cur = self.con.cursor()

    def execute(self, *args, **kwargs):
        sql = self.sub(args[0])
        new_args = (sql,) + args[1:]
        return self.cur.execute(*new_args, **kwargs)

    def fetchall(self):
        return self.cur.fetchall()

    def fetchone(self):
        return self.cur.fetchone()

    @staticmethod
    def sub(sql):
        sql = re.sub(r"CHARSET.*|charset.*", "", sql, re.IGNORECASE)
        sql = sql.replace("%s", "?")
        return sql


if __name__ == '__main__':
    con = FakeMySQL()
    cur = con.cursor()
    cur.execute("create table user(id int, name varchar(20))")
    cur.execute("insert into user values(%s,%s)", (1, "benny"))
    cur.execute("select * from user")
    data = cur.fetchall()
    print(data)
