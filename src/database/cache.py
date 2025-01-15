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

    def add_cache(self, key, mapping):
        self.r.hset(key, mapping=mapping)

    def get_cache(self, k: str):
        return self.r.hgetall(k)
