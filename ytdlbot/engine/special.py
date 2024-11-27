#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - special.py
# 3/16/24 16:32
#

__author__ = "SanujaNS <sanujas@sanuja.biz>"

import os
import re
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup


def special_download_entrance(url: str, tempdir: str, bm, **kwargs) -> list:
    """Specific link downloader"""
    domain = urlparse(url).hostname
    if "youtube.com" in domain or "youtu.be" in domain:
        raise ValueError("ERROR: This is ytdl bot for Youtube links just send the link.")
    elif "www.instagram.com" in domain:
        return instagram(url, tempdir, bm, **kwargs)
    elif "pixeldrain.com" in domain:
        return pixeldrain(url, tempdir, bm, **kwargs)
    elif "krakenfiles.com" in domain:
        return krakenfiles(url, tempdir, bm, **kwargs)
    else:
        raise ValueError(f"Invalid URL: No specific link function found for {url}")


def pixeldrain(url: str, tempdir: str, bm, **kwargs):
    user_page_url_regex = r"https://pixeldrain.com/u/(\w+)"
    match = re.match(user_page_url_regex, url)
    if match:
        url = "https://pixeldrain.com/api/file/{}?engine".format(match.group(1))
        return sp_ytdl_download(url, tempdir, bm, **kwargs)
    else:
        return url


def krakenfiles(url: str, tempdir: str, bm, **kwargs):
    resp = requests.get(url)
    html = resp.content
    soup = BeautifulSoup(html, "html.parser")
    link_parts = []
    token_parts = []
    for form_tag in soup.find_all("form"):
        action = form_tag.get("action")
        if action and "krakenfiles.com" in action:
            link_parts.append(action)
        input_tag = form_tag.find("input", {"name": "token"})
        if input_tag:
            value = input_tag.get("value")
            token_parts.append(value)
    for link_part, token_part in zip(link_parts, token_parts):
        link = f"https:{link_part}"
        data = {"token": token_part}
        response = requests.post(link, data=data)
        json_data = response.json()
        url = json_data["url"]
    return sp_ytdl_download(url, tempdir, bm, **kwargs)
