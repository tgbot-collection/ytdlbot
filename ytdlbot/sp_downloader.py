#!/usr/local/bin/python3
# coding: utf-8

# ytdlbot - sp_downloader.py
# 3/16/24 16:32
#

__author__ = "SanujaNS <sanujas@sanuja.biz>"

import functools
import os
import json
import logging
import pathlib
import re
import traceback
from urllib.parse import urlparse, parse_qs

from pyrogram import types
from tqdm import tqdm
import filetype
import requests
from bs4 import BeautifulSoup
import yt_dlp as ytdl

from config import (
    PREMIUM_USER,
    TG_NORMAL_MAX_SIZE,
    TG_PREMIUM_MAX_SIZE,
    FileTooBig,
    IPv6,
)
from downloader import (
    edit_text,
    remove_bash_color,
    ProgressBar,
    tqdm_progress,
    download_hook,
    upload_hook,
)
from limit import Payment
from utils import sizeof_fmt, parse_cookie_file, extract_code_from_instagram_url


def sp_dl(url: str, tempdir: str, bm, **kwargs) -> list:
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
    elif any(
        x in domain
        for x in [
            "terabox.com",
            "nephobox.com",
            "4funbox.com",
            "mirrobox.com",
            "momerybox.com",
            "teraboxapp.com",
            "1024tera.com",
            "terabox.app",
            "gibibox.com",
            "goaibox.com",
        ]
    ):
        return terabox(url, tempdir, bm, **kwargs)
    else:
        raise ValueError(f"Invalid URL: No specific link function found for {url}")
    
    return []


def sp_ytdl_download(url: str, tempdir: str, bm, filename=None, **kwargs) -> list:
    payment = Payment()
    chat_id = bm.chat.id
    if filename:
        output = pathlib.Path(tempdir, filename).as_posix()
    else:
        output = pathlib.Path(tempdir, "%(title).70s.%(ext)s").as_posix()
    ydl_opts = {
        "progress_hooks": [lambda d: download_hook(d, bm)],
        "outtmpl": output,
        "restrictfilenames": False,
        "quiet": True,
        "format": None,
    }

    address = ["::", "0.0.0.0"] if IPv6 else [None]
    error = None
    video_paths = None
    for addr in address:
        ydl_opts["source_address"] = addr
        try:
            logging.info("Downloading %s", url)
            with ytdl.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            video_paths = list(pathlib.Path(tempdir).glob("*"))
            break
        except FileTooBig as e:
                raise e
        except Exception:
            error = traceback.format_exc()
            logging.error("Download failed for %s - %s", url)

    if not video_paths:
        raise Exception(error)

    return video_paths


def instagram(url: str, tempdir: str, bm, **kwargs):
    resp = requests.get(f"http://192.168.6.1:15000/?url={url}").json()
    code = extract_code_from_instagram_url(url)
    counter = 1
    video_paths = []
    if url_results := resp.get("data"):
        for link in url_results:
            req = requests.get(link, stream=True)
            length = int(req.headers.get("content-length"))
            content = req.content
            ext = filetype.guess_extension(content)
            filename = f"{code}_{counter}.{ext}"
            save_path = pathlib.Path(tempdir, filename)
            chunk_size = 4096
            downloaded = 0
            for chunk in req.iter_content(chunk_size):
                text = tqdm_progress(f"Downloading: {filename}", length, downloaded)
                edit_text(bm, text)
                with open(save_path, "ab") as fp:
                    fp.write(chunk)
                downloaded += len(chunk)
            video_paths.append(save_path)
            counter += 1

    return video_paths


def pixeldrain(url: str, tempdir: str, bm, **kwargs):
    user_page_url_regex = r"https://pixeldrain.com/u/(\w+)"
    match = re.match(user_page_url_regex, url)
    if match:
        url = "https://pixeldrain.com/api/file/{}?download".format(match.group(1))
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
        data = {
            "token": token_part
        }
        response = requests.post(link, data=data)
        json_data = response.json()
        url = json_data["url"]
    return sp_ytdl_download(url, tempdir, bm, **kwargs)


def find_between(s, start, end):
    return (s.split(start))[1].split(end)[0]

def terabox(url: str, tempdir: str, bm, **kwargs):
    cookies_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "terabox.txt")
    cookies = parse_cookie_file(cookies_file)
    
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
        "Connection": "keep-alive",
        "DNT": "1",
        "Host": "www.terabox.app",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "sec-ch-ua": "'Not A(Brand';v='99', 'Google Chrome';v='121', 'Chromium';v='121'",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "'Windows'",
    }
    
    session = requests.Session()
    session.headers.update(headers)
    session.cookies.update(cookies)
    temp_req = session.get(url)
    request_url = urlparse(temp_req.url)
    surl = parse_qs(request_url.query).get("surl")
    req = session.get(temp_req.url)
    respo = req.text
    js_token = find_between(respo, "fn%28%22", "%22%29")
    logid = find_between(respo, "dp-logid=", "&")
    bdstoken = find_between(respo, 'bdstoken":"', '"')
    
    params = {
        "app_id": "250528",
        "web": "1",
        "channel": "dubox",
        "clienttype": "0",
        "jsToken": js_token,
        "dp-logid": logid,
        "page": "1",
        "num": "20",
        "by": "name",
        "order": "asc",
        "site_referer": temp_req.url,
        "shorturl": surl,
        "root": "1,",
    }
    
    req2 = session.get("https://www.terabox.app/share/list", params=params)
    response_data2 = req2.json()
    file_name = response_data2["list"][0]["server_filename"]
    sizebytes = int(response_data2["list"][0]["size"])
    if sizebytes > 48 * 1024 * 1024:
        direct_link = response_data2["list"][0]["dlink"]
        url = direct_link.replace("d.terabox.app", "d3.terabox.app")
    else:
        direct_link_response = session.head(response_data2["list"][0]["dlink"])
        direct_link_response_headers = direct_link_response.headers
        direct_link = direct_link_response_headers["Location"]
        url = direct_link
    
    return sp_ytdl_download(url, tempdir, bm, filename=file_name, **kwargs)