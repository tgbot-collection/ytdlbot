#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - pixeldrain.py

__author__ = "SanujaNS <sanujas@sanuja.biz>"

import re


def pixeldrain(url: str, tempdir: str, bm, **kwargs):
    user_page_url_regex = r"https://pixeldrain.com/u/(\w+)"
    match = re.match(user_page_url_regex, url)
    if match:
        url = "https://pixeldrain.com/api/file/{}?engine".format(match.group(1))
        return sp_ytdl_download(url, tempdir, bm, **kwargs)
    else:
        return url
