#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - types.py

import logging
import re
import tempfile
import uuid
from abc import ABC, abstractmethod
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import ffmpeg
import filetype
from pyrogram import enums, types
from tqdm import tqdm

from config import TG_NORMAL_MAX_SIZE, Types
from database import Redis
from database.model import (
    get_quality_settings,
    get_free_quota,
    get_paid_quota,
    get_format_settings,
    use_quota,
)
from engine.helper import debounce, sizeof_fmt


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
    def __init__(self, client: Types.Client, bot_msg: Types.Message, url: str):
        self._client = client
        self._url = url
        self._user_id = getattr(bot_msg.from_user, "id", None) or bot_msg.chat.id
        self._id = bot_msg.id
        self._tempdir = tempfile.TemporaryDirectory(prefix="ytdl-")
        self._bot_msg: Types.Message = bot_msg
        self._redis = Redis()
        self._record_usage()

    def __del__(self):
        self._tempdir.cleanup()

    def _record_usage(self):
        free, paid = get_free_quota(self._user_id), get_paid_quota(self._user_id)
        logging.info("User %s has %s free and %s paid quota", self._user_id, free, paid)
        if free + paid < 0:
            raise Exception("Usage limit exceeded")

        use_quota(self._user_id)

    @staticmethod
    def __remove_bash_color(text):
        return re.sub(r"\u001b|\[0;94m|\u001b\[0m|\[0;32m|\[0m|\[0;33m", "", text)

    @staticmethod
    def __tqdm_progress(desc, total, finished, speed="", eta=""):
        def more(title, initial):
            if initial:
                return f"{title} {initial}"
            else:
                return ""

        f = StringIO()
        tqdm(
            total=total,
            initial=finished,
            file=f,
            ascii=False,
            unit_scale=True,
            ncols=30,
            bar_format="{l_bar}{bar} |{n_fmt}/{total_fmt} ",
        )
        raw_output = f.getvalue()
        tqdm_output = raw_output.split("|")
        progress = f"`[{tqdm_output[1]}]`"
        detail = tqdm_output[2].replace("[A", "")
        text = f"""
    {desc}

    {progress}
    {detail}
    {more("Speed:", speed)}
    {more("ETA:", eta)}
        """
        f.close()
        return text

    def download_hook(self, d: dict):
        if d["status"] == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)

            if total > TG_NORMAL_MAX_SIZE:
                msg = f"Your download file size {sizeof_fmt(total)} is too large for Telegram."
                raise Exception(msg)

            # percent = remove_bash_color(d.get("_percent_str", "N/A"))
            speed = self.__remove_bash_color(d.get("_speed_str", "N/A"))
            eta = self.__remove_bash_color(d.get("_eta_str", d.get("eta")))
            text = self.__tqdm_progress("Downloading...", total, downloaded, speed, eta)
            self.edit_text(text)

    def upload_hook(self, current, total):
        text = self.__tqdm_progress("Uploading...", total, current)
        self.edit_text(text)

    @debounce(5)
    def edit_text(self, text: str):
        self._bot_msg.edit_text(text)

    def get_cache_fileid(self):
        unique = self._url + get_quality_settings(self._url)
        return self._redis.get_send_cache(unique)

    @abstractmethod
    def _setup_formats(self) -> list | None:
        pass

    @abstractmethod
    def _download(self, formats) -> list:
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
        self._client.send_chat_action(chat_id, enums.ChatAction.UPLOAD_DOCUMENT)
        if len(files) > 1:
            inputs = generate_input_media(files, caption)
            return self._client.send_media_group(chat_id, inputs)[0]
        else:
            return self._methods[_type](
                chat_id,
                files[0],
                caption=caption,
                thumb=thumb,
                progress=self.upload_hook,
                # progress_args=(self._bot_msg,),
                **kwargs,
            )

    def get_metadata(self):
        video_path = list(Path(self._tempdir.name).glob("*"))[0]
        filename = Path(video_path).name
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

        caption = f"{self._url}\n{filename}\n\nResolution: {width}x{height}\nDuration: {duration} seconds"
        return dict(height=height, width=width, duration=duration, thumb=thumb, caption=caption)

    def _upload(self):
        upload = get_format_settings(self._user_id)
        # we only support single file upload
        files = list(Path(self._tempdir.name).glob("*"))
        meta = self.get_metadata()

        success = SimpleNamespace(document=None, video=None, audio=None, animation=None, photo=None)
        if upload == "document":
            success = self.send_something(
                chat_id=self._user_id,
                files=files,
                _type="document",
                thumb=meta["thumb"],
                force_document=True,
                caption=meta["caption"],
            )
        elif upload == "audio":
            success = self.send_something(
                chat_id=self._user_id,
                files=files,
                _type="audio",
                caption=meta["caption"],
            )
        elif upload == "video":
            methods = {"video": meta, "animation": {}, "photo": {}}
            for method, thumb in methods.items():
                try:
                    success = self.send_something(chat_id=self._user_id, files=files, _type=method, **meta)
                    break
                except Exception as e:
                    logging.error("Retry to send as %s, error:", method, e)
        else:
            logging.error("Unknown upload settings")
            return

        # unique link is link+download_format
        unique = self._url + get_quality_settings(self._url) + upload
        obj = success.document or success.video or success.audio or success.animation or success.photo
        self._redis.add_send_cache(unique, getattr(obj, "file_id", None), upload)
        # change progress bar to done
        self._bot_msg.edit_text("✅ Success")
        return success

    @abstractmethod
    def start(self):
        pass
