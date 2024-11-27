#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - video.py

import re

import requests


def video_download_entrance():
    pass


def extract_code_from_instagram_url(url):
    # Regular expression patterns
    patterns = [
        # Instagram stories highlights
        r"/stories/highlights/([a-zA-Z0-9_-]+)/",
        # Posts
        r"/p/([a-zA-Z0-9_-]+)/",
        # Reels
        r"/reel/([a-zA-Z0-9_-]+)/",
        # TV
        r"/tv/([a-zA-Z0-9_-]+)/",
        # Threads post (both with @username and without)
        r"(?:https?://)?(?:www\.)?(?:threads\.net)(?:/[@\w.]+)?(?:/post)?/([\w-]+)(?:/?\?.*)?$"
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            if pattern == patterns[0]:  # Check if it's the stories highlights pattern
                # Return the URL as it is
                return url
            else:
                # Return the code part (first group)
                return match.group(1)

    return None


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
