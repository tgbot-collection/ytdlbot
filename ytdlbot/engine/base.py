#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - types.py

import logging
import tempfile
from abc import ABC, abstractmethod

from config import Types
from database.model import (
    get_free_quota,
    get_paid_quota,
    get_upload_settings,
    use_quota,
)


def record_usage(func):
    def wrapper(self, *args, **kwargs):
        free, paid = get_free_quota(self._user_id), get_paid_quota(self._user_id)
        if free + paid < 0:
            raise Exception("Usage limit exceeded")
        # check cache first
        if self.check_cache():
            result = None
        else:
            result = func(self, *args, **kwargs)  # Call the original method
        use_quota(self._user_id)
        return result

    return wrapper


class BaseDownloader(ABC):
    def __init__(self, client: Types.Client, url: str, user_id: int, _id: int):
        self._client = client
        self._url = url
        self._user_id = user_id
        self._id = _id
        self._tempdir = tempfile.TemporaryDirectory(prefix="ytdl-")
        self._bot_msg = self._client.get_messages(self._user_id, self._id)

    def __del__(self):
        self._tempdir.cleanup()

    def check_cache(self):
        print(self._url)
        return True

    @abstractmethod
    def _setup_formats(self):
        pass

    @abstractmethod
    def _download(self, formats):
        pass

    def _upload(self, path):
        upload = get_upload_settings(self._user_id)
        # path, caption, upload format, etc.
        # raise pyrogram.errors.exceptions.FloodWait(13)
        # if is str, it's a file id; else it's a list of paths
        chat_id = bot_msg.chat.id
        markup = gen_video_markup()
        if isinstance(vp_or_fid, list) and len(vp_or_fid) > 1:
            # just generate the first for simplicity, send as media group(2-20)
            cap, meta = gen_cap(bot_msg, url, vp_or_fid[0])
            res_msg: list[Types.Message] = self._client.send_media_group(chat_id, generate_input_media(vp_or_fid, cap))
            # TODO no cache for now
            return res_msg[0]
        elif isinstance(vp_or_fid, list) and len(vp_or_fid) == 1:
            # normal engine, just contains one file in video_paths
            vp_or_fid = vp_or_fid[0]
            cap, meta = gen_cap(bot_msg, url, vp_or_fid)
        else:
            # just a file id as string
            cap, meta = gen_cap(bot_msg, url, vp_or_fid)

        settings = payment.get_user_settings(chat_id)

        if settings[2] == "document":
            logging.info("Sending as document")
            try:
                # send as document could be sent as video even if it's a document
                res_msg = self._client.send_document(
                    chat_id,
                    vp_or_fid,
                    caption=cap,
                    progress=upload_hook,
                    progress_args=(bot_msg,),
                    reply_markup=markup,
                    thumb=meta["thumb"],
                    force_document=True,
                )
            except ValueError:
                logging.error("Retry to send as video")
                res_msg = self._client.send_video(
                    chat_id,
                    vp_or_fid,
                    supports_streaming=True,
                    caption=cap,
                    progress=upload_hook,
                    progress_args=(bot_msg,),
                    reply_markup=markup,
                    **meta,
                )
        elif settings[2] == "audio":
            logging.info("Sending as audio")
            res_msg = self._client.send_audio(
                chat_id,
                vp_or_fid,
                caption=cap,
                progress=upload_hook,
                progress_args=(bot_msg,),
            )
        else:
            # settings==video
            logging.info("Sending as video")
            try:
                res_msg = self._client.send_video(
                    chat_id,
                    vp_or_fid,
                    supports_streaming=True,
                    caption=cap,
                    progress=upload_hook,
                    progress_args=(bot_msg,),
                    reply_markup=markup,
                    **meta,
                )
            except Exception:
                # try to send as annimation, photo
                try:
                    logging.warning("Retry to send as animation")
                    res_msg = self._client.send_animation(
                        chat_id,
                        vp_or_fid,
                        caption=cap,
                        progress=upload_hook,
                        progress_args=(bot_msg,),
                        reply_markup=markup,
                        **meta,
                    )
                except Exception:
                    # this is likely a photo
                    logging.warning("Retry to send as photo")
                    res_msg = self._client.send_photo(
                        chat_id,
                        vp_or_fid,
                        caption=cap,
                        progress=upload_hook,
                        progress_args=(bot_msg,),
                    )

        unique = get_unique_clink(url, bot_msg.chat.id)
        obj = res_msg.document or res_msg.video or res_msg.audio or res_msg.animation or res_msg.photo
        redis.add_send_cache(unique, getattr(obj, "file_id", None))
        return res_msg

    @abstractmethod
    def start(self):
        pass
