#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - broadcast.py
# 8/25/21 16:11
#

__author__ = "Benny <benny.think@gmail.com>"

import argparse
import contextlib
import logging
import random
import sys
import tempfile
import time

from tqdm import tqdm

from limit import Redis
from ytdl import create_app

parser = argparse.ArgumentParser(description='Broadcast to users')
parser.add_argument('-m', help='message', required=True)
parser.add_argument('-p', help='picture', default=None)
parser.add_argument('--notify', help='notify all users?', action="store_false")
parser.add_argument('-u', help='user_id', type=int)
logging.basicConfig(level=logging.INFO)
args = parser.parse_args()

r = Redis().r
keys = r.keys("*")
user_ids = set()
for key in keys:
    if key.isdigit():
        user_ids.add(key)

metrics = r.hgetall("metrics")

for key in metrics:
    if key.isdigit():
        user_ids.add(key)

if args.u:
    user_ids = [args.u]

if "YES" != input("Are you sure you want to send broadcast message to %s users?\n>" % len(user_ids)):
    logging.info("Abort")
    sys.exit(1)

with tempfile.NamedTemporaryFile() as tmp:
    app = create_app(tmp.name, 1)
    app.start()
    for user_id in tqdm(user_ids):
        time.sleep(random.random() * 5)
        if args.p:
            with contextlib.suppress(Exception):
                app.send_photo(user_id, args.p, caption=args.m, disable_notification=args.notify)
        else:
            with contextlib.suppress(Exception):
                app.send_message(user_id, args.m, disable_notification=args.notify)
    app.stop()
