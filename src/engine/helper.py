#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - helper.py

import functools
import logging
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from http import HTTPStatus
from io import StringIO

import ffmpeg
import ffpb
import filetype
import pyrogram
import requests
import yt_dlp
from bs4 import BeautifulSoup
from pyrogram import types
from tqdm import tqdm

from config import (
    AUDIO_FORMAT,
    CAPTION_URL_LENGTH_LIMIT,
    ENABLE_ARIA2,
    TG_NORMAL_MAX_SIZE,
)
from utils import shorten_url, sizeof_fmt


def debounce(wait_seconds):
    """
    Thread-safe debounce decorator for functions that take a message with chat.id and msg.id attributes.
    The function will only be called if it hasn't been called with the same chat.id and msg.id in the last 'wait_seconds'.
    """

    def decorator(func):
        last_called = {}
        lock = threading.Lock()

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal last_called
            now = time.time()

            # Assuming the first argument is the message object with chat.id and msg.id
            bot_msg = args[0]._bot_msg
            key = (bot_msg.chat.id, bot_msg.id)

            with lock:
                if key not in last_called or now - last_called[key] >= wait_seconds:
                    last_called[key] = now
                    return func(*args, **kwargs)

        return wrapper

    return decorator


def get_caption(url, video_path):
    if isinstance(video_path, Path):
        meta = get_metadata(video_path)
        file_name = video_path.name
        file_size = sizeof_fmt(os.stat(video_path).st_size)
    else:
        file_name = getattr(video_path, "file_name", "")
        file_size = sizeof_fmt(getattr(video_path, "file_size", (2 << 2) + ((2 << 2) + 1) + (2 << 5)))
        meta = dict(
            width=getattr(video_path, "width", 0),
            height=getattr(video_path, "height", 0),
            duration=getattr(video_path, "duration", 0),
            thumb=getattr(video_path, "thumb", None),
        )

    # Shorten the URL if necessary
    try:
        if len(url) > CAPTION_URL_LENGTH_LIMIT:
            url_for_cap = shorten_url(url, CAPTION_URL_LENGTH_LIMIT)
        else:
            url_for_cap = url
    except Exception as e:
        logging.warning(f"Error shortening URL: {e}")
        url_for_cap = url

    cap = (
        f"{file_name}\n\n{url_for_cap}\n\nInfo: {meta['width']}x{meta['height']} {file_size}\t" f"{meta['duration']}s\n"
    )
    return cap


def convert_audio_format(video_paths: list, bm):
    # 1. file is audio, default format
    # 2. file is video, default format
    # 3. non default format

    for path in video_paths:
        streams = ffmpeg.probe(path)["streams"]
        if AUDIO_FORMAT is None and len(streams) == 1 and streams[0]["codec_type"] == "audio":
            logging.info("%s is audio, default format, no need to convert", path)
        elif AUDIO_FORMAT is None and len(streams) >= 2:
            logging.info("%s is video, default format, need to extract audio", path)
            audio_stream = {"codec_name": "m4a"}
            for stream in streams:
                if stream["codec_type"] == "audio":
                    audio_stream = stream
                    break
            ext = audio_stream["codec_name"]
            new_path = path.with_suffix(f".{ext}")
            run_ffmpeg_progressbar(["ffmpeg", "-y", "-i", path, "-vn", "-acodec", "copy", new_path], bm)
            path.unlink()
            index = video_paths.index(path)
            video_paths[index] = new_path
        else:
            logging.info("Not default format, converting %s to %s", path, AUDIO_FORMAT)
            new_path = path.with_suffix(f".{AUDIO_FORMAT}")
            run_ffmpeg_progressbar(["ffmpeg", "-y", "-i", path, new_path], bm)
            path.unlink()
            index = video_paths.index(path)
            video_paths[index] = new_path


def ensure_streamable_video(video_path: Path) -> Path:
    video_path = Path(video_path)
    mime = filetype.guess_mime(str(video_path))
    if mime and "video" not in mime:
        return video_path

    try:
        probe = ffmpeg.probe(str(video_path))
        video_codec = None
        width = 0
        height = 0
        for stream in probe.get("streams", []):
            if stream["codec_type"] == "video":
                video_codec = stream["codec_name"]
                width = stream.get("width", 0) or 0
                height = stream.get("height", 0) or 0
                break

        ext = video_path.suffix.lower()
        # Always re-encode if video exceeds 720p, regardless of format
        # Skip only if already mp4/h264 AND within 720p limits
        max_dimension = max(width, height)
        should_skip = (ext == ".mp4" and video_codec == "h264" and max_dimension <= 720)
        
        if should_skip:
            logging.info("Video already compliant: %s (%dx%d), skipping", video_path, width, height)
            return video_path

        logging.info(
            "Re-encoding %s: %s (%s, %dx%d) -> max 720p",
            video_path, video_codec, ext, width, height,
        )
        new_path = video_path.with_suffix(".mp4")
        # Write to a temp file first to avoid in-place overwrite when
        # video_path already has .mp4 extension (ffmpeg can't read+write same file).
        temp_path = video_path.with_suffix(".tmp.mp4")

        # Build scale filter: resize to max 720p while preserving aspect ratio
        # -2 ensures divisibility by 2. The largest dimension is capped to 720.
        # If video is already ≤720p, should_skip above already returned early.
        if width > height:
            # Horizontal video: limit width to 720, height auto
            scale_filter = "scale=720:-2"
        else:
            # Vertical or square video: limit height to 720, width auto
            scale_filter = "scale=-2:720"

        args = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vcodec", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            "-acodec", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            "-vf", scale_filter,
            str(temp_path),
        ]

        logging.info("ffmpeg: %s", " ".join(args))
        subprocess.run(args, check=True, capture_output=True, timeout=600)

        if not temp_path.exists() or temp_path.stat().st_size == 0:
            raise RuntimeError(f"ffmpeg produced empty or missing file: {temp_path}")
        video_path.unlink()
        temp_path.rename(new_path)
        return new_path
    except subprocess.TimeoutExpired:
        logging.error("ffmpeg timed out for %s after 600s", video_path)
        return video_path
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else str(e)
        logging.error("ffmpeg error for %s\nstderr: %s", video_path, stderr)
        return video_path
    except Exception as e:
        logging.error("ensure_streamable_video failed for %s", video_path, exc_info=True)
        return video_path


def split_large_video(video_paths: list):
    original_video = None
    split = False
    for original_video in video_paths:
        size = os.stat(original_video).st_size
        if size > TG_NORMAL_MAX_SIZE:
            split = True
            logging.warning("file is too large %s, splitting...", size)
            subprocess.check_output(f"sh split-video.sh {original_video} {TG_NORMAL_MAX_SIZE * 0.95} ".split())
            os.remove(original_video)

    if split and original_video:
        return [i for i in Path(original_video).parent.glob("*")]
