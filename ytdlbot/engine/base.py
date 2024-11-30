#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - types.py

import logging
import tempfile
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from types import SimpleNamespace

import ffmpeg
import filetype
from helper import get_caption, upload_hook
from pyrogram import types

from config import Types
from database import Redis
from database.model import (
    get_download_settings,
    get_free_quota,
    get_paid_quota,
    get_upload_settings,
    use_quota,
)


def record_usage(func):
    def wrapper(self: BaseDownloader, *args, **kwargs):
        free, paid = get_free_quota(self._user_id), get_paid_quota(self._user_id)
        if free + paid < 0:
            raise Exception("Usage limit exceeded")
        # check cache first
        result = None
        if caches := self.get_cache_fileid():
            for fid, _type in caches.items():
                self._methods[caches[_type]](self._user_id, fid)
        else:
            result = func(self, *args, **kwargs)  # Call the original method
        use_quota(self._user_id)
        return result

    return wrapper


def generate_input_media(file_paths: list, cap: str) -> list:
    input_media = []
    for path in file_paths:
        mime = filetype.guess_mime(path)
        if "video" in mime:
            input_media.append(types.InputMediaVideo(media=path))
        elif "image" in mime:
            input_media.append(types.InputMediaPhoto(media=path))
        elif "audio" in mime:
            input_media.append(types.InputMediaAudio(media=path))
        else:
            input_media.append(types.InputMediaDocument(media=path))

    input_media[0].caption = cap
    return input_media


class BaseDownloader(ABC):
    def __init__(self, client: Types.Client, url: str, user_id: int, _id: int):
        self._client = client
        self._url = url
        self._user_id = user_id
        self._id = _id
        self._tempdir = tempfile.TemporaryDirectory(prefix="ytdl-")
        self._bot_msg: Types.Message = self._client.get_messages(self._user_id, self._id)
        self._redis = Redis()

    def __del__(self):
        self._tempdir.cleanup()

    def get_cache_fileid(self):
        unique = self._url + get_download_settings(self._url)
        return self._redis.get_send_cache(unique)

    @abstractmethod
    def _setup_formats(self):
        pass

    @abstractmethod
    def _download(self, formats):
        # responsible for get format and download it
        pass

    @property
    def _methods(self):
        return {
            "document": self._client.send_document,
            "audio": self._client.send_audio,
            "video": self._client.send_video,
            "animation": self._client.send_animation,
            "photo": self._client.send_photo,
        }

    def send_something(self, *, chat_id, files, _type, caption=None, thumb=None, **kwargs):
        if len(files) > 1:
            inputs = generate_input_media(files, caption)
            return self._client.send_media_group(chat_id, inputs)[0]
        else:
            return self._methods[_type](
                chat_id,
                files[0],
                caption=caption,
                thumb=thumb,
                progress=upload_hook,
                progress_args=(self._bot_msg,),
                **kwargs,
            )

    @staticmethod
    def get_metadata(files):
        video_path = files[0]
        width = height = duration = 0
        try:
            video_streams = ffmpeg.probe(video_path, select_streams="v")
            for item in video_streams.get("streams", []):
                height = item["height"]
                width = item["width"]
            duration = int(float(video_streams["format"]["duration"]))
        except Exception as e:
            logging.error(e)
        try:
            thumb = Path(video_path).parent.joinpath(f"{uuid.uuid4().hex}-thunmnail.png").as_posix()
            # A thumbnail's width and height should not exceed 320 pixels.
            ffmpeg.input(video_path, ss=duration / 2).filter(
                "scale",
                "if(gt(iw,ih),300,-1)",  # If width > height, scale width to 320 and height auto
                "if(gt(iw,ih),-1,300)",
            ).output(thumb, vframes=1).run()
        except ffmpeg._run.Error:
            thumb = None

        return dict(height=height, width=width, duration=duration, thumb=thumb)

    @record_usage
    def _upload(self):
        upload = get_upload_settings(self._user_id)
        chat_id = self._bot_msg.chat.id
        files = list(Path(self._tempdir.name).glob("*"))

        success = SimpleNamespace(document=None, video=None, audio=None, animation=None, photo=None)
        if upload == "document":
            thumb = self.get_metadata(files)["thumb"]
            success = self.send_something(
                chat_id=chat_id,
                files=files,
                _type="document",
                thumb=thumb,
                force_document=True,
            )
        elif upload == "audio":
            success = self.send_something(chat_id=chat_id, files=files, _type="audio")
        elif upload == "video":
            methods = {"video": self.get_metadata(files)["thumb"], "animation": None, "photo": None}
            for method, thumb in methods.items():
                try:
                    success = self.send_something(chat_id=chat_id, files=files, _type=method, thumb=thumb)
                    break
                except Exception:
                    logging.error("Retry to send as %s", method)
        else:
            logging.error("Unknown upload settings")
            return

        # unique link is link+download_format
        unique = self._url + get_download_settings(self._url)
        obj = success.document or success.video or success.audio or success.animation or success.photo
        self._redis.add_send_cache(unique, getattr(obj, "file_id", None), upload)
        return success

    @abstractmethod
    def start(self):
        pass
