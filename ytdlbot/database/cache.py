#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - cache.py


import logging

import fakeredis
import redis

from config import REDIS_HOST


class Redis:
    def __init__(self):
        try:
            self.r = redis.StrictRedis(host=REDIS_HOST, db=1, decode_responses=True)
            self.r.ping()
        except Exception:
            logging.warning("Redis connection failed, using fake redis instead.")
            self.r = fakeredis.FakeStrictRedis(host=REDIS_HOST, db=1, decode_responses=True)

    def __del__(self):
        self.r.close()

    def reset_today(self):
        pass

    def user_count(self, user_id):
        self.r.hincrby("metrics", user_id)

    def add_send_cache(self, unique: str, file_id: str):
        self.r.hset("cache", unique, file_id)

    def get_send_cache(self, unique) -> str:
        return self.r.hget("cache", unique)

    def del_send_cache(self, unique):
        return self.r.hdel("cache", unique)
