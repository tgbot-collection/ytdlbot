#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - normal.py

import pathlib


def ytdl_download_function(url: str, tempdir: str, bm, **kwargs) -> list:

    output = pathlib.Path(tempdir, "%(title).70s.%(ext)s").as_posix()
    ydl_opts = {
        "progress_hooks": [lambda d: download_hook(d, bm)],
        "outtmpl": output,
        "restrictfilenames": False,
        "quiet": True,
    }
    if ENABLE_ARIA2:
        ydl_opts["external_downloader"] = "aria2c"
        ydl_opts["external_downloader_args"] = [
            "--min-split-size=1M",
            "--max-connection-per-server=16",
            "--max-concurrent-downloads=16",
            "--split=16",
        ]
    if url.startswith("https://drive.google.com"):
        # Always use the `source` format for Google Drive URLs.
        formats = ["source"]
    else:
        # Use the default formats for other URLs.
        formats = [
            # webm , vp9 and av01 are not streamable on telegram, so we'll extract only mp4
            "bestvideo[ext=mp4][vcodec!*=av01][vcodec!*=vp09]+bestaudio[ext=m4a]/bestvideo+bestaudio",
            "bestvideo[vcodec^=avc]+bestaudio[acodec^=mp4a]/best[vcodec^=avc]/best",
            None,
        ]
    # This method will alter formats if necessary

    error = None
    video_paths = None
    for format_ in formats:
        ydl_opts["format"] = format_
        with ytdl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        video_paths = list(pathlib.Path(tempdir).glob("*"))

    return video_paths
