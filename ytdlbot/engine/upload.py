#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - upload.py
import logging

from config import Types


def forward_video(client, bot_msg: Types.Message, url: str, cached_fid: str):
    res_msg = upload_processor(client, bot_msg, url, cached_fid)
    obj = res_msg.document or res_msg.video or res_msg.audio or res_msg.animation or res_msg.photo

    caption, _ = gen_cap(bot_msg, url, obj)
    res_msg.edit_text(caption, reply_markup=gen_video_markup())
    bot_msg.edit_text(f"Download success!✅")
    return True


def upload_processor(client: Types.Client, bot_msg: Types.Message, url: str, vp_or_fid: str | list):
    # raise pyrogram.errors.exceptions.FloodWait(13)
    # if is str, it's a file id; else it's a list of paths
    chat_id = bot_msg.chat.id
    markup = gen_video_markup()
    if isinstance(vp_or_fid, list) and len(vp_or_fid) > 1:
        # just generate the first for simplicity, send as media group(2-20)
        cap, meta = gen_cap(bot_msg, url, vp_or_fid[0])
        res_msg: list[Types.Message] = client.send_media_group(chat_id, generate_input_media(vp_or_fid, cap))
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
            res_msg = client.send_document(
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
            res_msg = client.send_video(
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
        res_msg = client.send_audio(
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
            res_msg = client.send_video(
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
                res_msg = client.send_animation(
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
                res_msg = client.send_photo(
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
