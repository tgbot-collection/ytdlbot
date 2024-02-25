#!/usr/bin/env python3
# coding: utf-8
import http
import logging
import os
import re

import requests
from bs4 import BeautifulSoup

from config import ENABLE_VIP
from limit import Payment


class Channel(Payment):
    def subscribe_channel(self, user_id: int, share_link: str) -> str:
        if not re.findall(r"youtube\.com|youtu\.be", share_link):
            raise ValueError("Is this a valid YouTube Channel link?")
        if ENABLE_VIP:
            self.cur.execute("select count(user_id) from subscribe where user_id=%s", (user_id,))
            usage = int(self.cur.fetchone()[0])
            if usage >= 10:
                logging.warning("User %s has subscribed %s channels", user_id, usage)
                return "You have subscribed too many channels. Maximum 5 channels."

        data = self.get_channel_info(share_link)
        channel_id = data["channel_id"]

        self.cur.execute("select user_id from subscribe where user_id=%s and channel_id=%s", (user_id, channel_id))
        if self.cur.fetchall():
            raise ValueError("You have already subscribed this channel.")

        self.cur.execute(
            "INSERT IGNORE INTO channel values"
            "(%(link)s,%(title)s,%(description)s,%(channel_id)s,%(playlist)s,%(last_video)s)",
            data,
        )
        self.cur.execute("INSERT INTO subscribe values(%s,%s, NULL)", (user_id, channel_id))
        self.con.commit()
        logging.info("User %s subscribed channel %s", user_id, data["title"])
        return "Subscribed to {}".format(data["title"])

    def unsubscribe_channel(self, user_id: int, channel_id: str) -> int:
        affected_rows = self.cur.execute(
            "DELETE FROM subscribe WHERE user_id=%s AND channel_id=%s", (user_id, channel_id)
        )
        self.con.commit()
        logging.info("User %s tried to unsubscribe channel %s", user_id, channel_id)
        return affected_rows

    @staticmethod
    def extract_canonical_link(url: str) -> str:
        # canonic link works for many websites. It will strip out unnecessary stuff
        props = ["canonical", "alternate", "shortlinkUrl"]
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36"
        }
        cookie = {"CONSENT": "PENDING+197"}
        # send head request first
        r = requests.head(url, headers=headers, allow_redirects=True, cookies=cookie)
        if r.status_code != http.HTTPStatus.METHOD_NOT_ALLOWED and "text/html" not in r.headers.get("content-type", ""):
            # get content-type, if it's not text/html, there's no need to issue a GET request
            logging.warning("%s Content-type is not text/html, no need to GET for extract_canonical_link", url)
            return url

        html_doc = requests.get(url, headers=headers, cookies=cookie, timeout=5).text
        soup = BeautifulSoup(html_doc, "html.parser")
        for prop in props:
            element = soup.find(lambda tag: tag.name == "link" and tag.get("rel") == ["prop"])
            try:
                href = element["href"]
                if href not in ["null", "", None, "https://consent.youtube.com/m"]:
                    return href
            except Exception as e:
                logging.debug("Canonical exception %s %s e", url, e)

        return url

    def get_channel_info(self, url: str) -> dict:
        api_key = os.getenv("GOOGLE_API_KEY")
        canonical_link = self.extract_canonical_link(url)
        try:
            channel_id = canonical_link.split("youtube.com/channel/")[1]
        except IndexError:
            channel_id = canonical_link.split("/")[-1]
        channel_api = (
            f"https://www.googleapis.com/youtube/v3/channels?part=snippet,contentDetails&id={channel_id}&key={api_key}"
        )

        data = requests.get(channel_api).json()
        snippet = data["items"][0]["snippet"]
        title = snippet["title"]
        description = snippet["description"]
        playlist = data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

        return {
            "link": url,
            "title": title,
            "description": description,
            "channel_id": channel_id,
            "playlist": playlist,
            "last_video": self.get_latest_video(playlist),
        }

    @staticmethod
    def get_latest_video(playlist_id: str) -> str:
        api_key = os.getenv("GOOGLE_API_KEY")
        video_api = (
            f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&maxResults=1&"
            f"playlistId={playlist_id}&key={api_key}"
        )
        data = requests.get(video_api).json()
        video_id = data["items"][0]["snippet"]["resourceId"]["videoId"]
        logging.info(f"Latest video %s from %s", video_id, data["items"][0]["snippet"]["channelTitle"])
        return f"https://www.youtube.com/watch?v={video_id}"

    def has_newer_update(self, channel_id: str) -> str:
        self.cur.execute("SELECT playlist,latest_video FROM channel WHERE channel_id=%s", (channel_id,))
        data = self.cur.fetchone()
        playlist_id = data[0]
        old_video = data[1]
        newest_video = self.get_latest_video(playlist_id)
        if old_video != newest_video:
            logging.info("Newer update found for %s %s", channel_id, newest_video)
            self.cur.execute("UPDATE channel SET latest_video=%s WHERE channel_id=%s", (newest_video, channel_id))
            self.con.commit()
            return newest_video

    def get_user_subscription(self, user_id: int) -> str:
        self.cur.execute(
            """
               select title, link, channel.channel_id from channel, subscribe 
               where subscribe.user_id = %s and channel.channel_id = subscribe.channel_id
            """,
            (user_id,),
        )
        data = self.cur.fetchall()
        text = ""
        for item in data:
            text += "[{}]({}) `{}\n`".format(*item)
        return text

    def group_subscriber(self) -> dict:
        # {"channel_id": [user_id, user_id, ...]}
        self.cur.execute("select * from subscribe where is_valid=1")
        data = self.cur.fetchall()
        group = {}
        for item in data:
            group.setdefault(item[1], []).append(item[0])
        logging.info("Checking periodic subscriber...")
        return group

    def deactivate_user_subscription(self, user_id: int):
        self.cur.execute("UPDATE subscribe set is_valid=0 WHERE user_id=%s", (user_id,))
        self.con.commit()

    def sub_count(self) -> str:
        sql = """
        select user_id, channel.title, channel.link
        from subscribe, channel where subscribe.channel_id = channel.channel_id
        """
        self.cur.execute(sql)
        data = self.cur.fetchall()
        text = f"Total {len(data)} subscriptions found.\n\n"
        for item in data:
            text += "{} ==> [{}]({})\n".format(*item)
        return text

    def del_cache(self, user_link: str) -> int:
        unique = self.extract_canonical_link(user_link)
        caches = self.r.hgetall("cache")
        count = 0
        for key in caches:
            if key.startswith(unique):
                count += self.del_send_cache(key)
        return count


if __name__ == "__main__":
    s = Channel.extract_canonical_link("https://www.youtube.com/shorts/KkbYbknjPBM")
    print(s)
