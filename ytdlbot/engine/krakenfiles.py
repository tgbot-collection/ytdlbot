#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - krakenfiles.py

__author__ = "SanujaNS <sanujas@sanuja.biz>"

import requests
from bs4 import BeautifulSoup


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
