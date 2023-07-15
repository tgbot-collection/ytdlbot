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
            raise ValueError("هل هذا رابط قناة يوتيوب صالح؟")
        if ENABLE_VIP:
            self.cur.execute("select count(user_id) from subscribe where user_id=%s", (user_id,))
            usage = int(self.cur.fetchone()[0])
            if usage >= 10:
                logging.warning("المستخدم %s اشترك في %s قنوات", user_id, usage)
                return "لقد اشتركت في الكثير من القنوات. الحد الأقصى 5 قنوات."

        data = self.get_channel_info(share_link)
        channel_id = data["channel_id"]

        self.cur.execute("select user_id from subscribe where user_id=%s and channel_id=%s", (user_id, channel_id))
        if self.cur.fetchall():
            raise ValueError("لقد اشتركت في هذه القناة بالفعل.")

        self.cur.execute(
            "INSERT IGNORE INTO channel values"
            "(%(link)s,%(title)s,%(description)s,%(channel_id)s,%(playlist)s,%(last_video)s)",
            data,
        )
        self.cur.execute("INSERT INTO subscribe values(%s,%s, NULL)", (user_id, channel_id))
        self.con.commit()
        logging.info("المستخدم %s اشترك في القناة %s", user_id, data["title"])
        return "تم الاشتراك في {}".format(data["title"])

    def unsubscribe_channel(self, user_id: int, channel_id: str) -> int:
        affected_rows = self.cur.execute(
            "DELETE FROM subscribe WHERE user_id=%s AND channel_id=%s", (user_id, channel_id)
        )
        self.con.commit()
        logging.info("المستخدم %s حاول إلغاء اشتراكه في القناة %s", user_id, channel_id)
        return affected_rows

    @staticmethod
    def extract_canonical_link(url: str) -> str:
        # canonic link works for many websites. It will strip out unnecessary stuff
        props = ["canonical", "alternate", "shortlinkUrl"]
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36"
        }
        cookie = {"CONSENT": "YES+cb.20210328-17-p0.en+FX+999"}
        # send head request first
        r = requests.head(url, headers=headers, allow_redirects=True, cookies=cookie)
        if r.status_code != http.HTTPStatus.METHOD_NOT_ALLOWED and "text/html" not in r.headers.get("content-type", ""):
            # get content-type, if it's not text/html, there's no need to issue a GET request
            logging.warning("%s نوع المحتوى ليس نصًا/HTML ، لا يوجد حاجة إلى GET لاستخراج الرابط الأساسي", url)
            return url

        html_doc = requests.get(url, headers=headers, cookies=cookie, timeout=5).text
        soup = BeautifulSoup(html_doc, "html.parser")
        for prop in props:
            element = soup.find("link", rel=prop)
            try:
                href = element["href"]
                if "youtube.com" in href or "youtu.be" in href:
                    return href
            except (TypeError, KeyError):
                pass
        return url

    def get_channel_info(self, share_link: str) -> dict:
        url = self.extract_canonical_link(share_link)
        channel_id = re.findall(r"channel\/([\w-]+)", url)
        if channel_id:
            channel_id = channel_id[0]
            r = requests.get(f"https://www.youtube.com/channel/{channel_id}/about", timeout=5)
            soup = BeautifulSoup(r.text, "html.parser")
            channel_title = soup.find("yt-formatted-string", {"class": "style-scope ytd-channel-name"}).text.strip()
            channel_description = (
                soup.find("div", {"id": "description-container"}).find("yt-formatted-string").text.strip()
            )
            playlist_id = soup.find("a", {"class": "yt-simple-endpoint style-scope yt-formatted-string"})["href"]
            last_video = soup.find("div", {"id": "date"}).find_all("yt-formatted-string")[1].text.strip()
            return {
                "link": share_link,
                "title": channel_title,
                "description": channel_description,
                "channel_id": channel_id,
                "playlist": playlist_id,
                "last_video": last_video,
            }
        else:
            raise ValueError("لا يمكن العثور على هوية القناة في الرابط.")

    def update_subscriptions(self):
        self.cur.execute(
            "SELECT link, channel_id FROM channel WHERE channel_id IN (SELECT channel_id FROM subscribe)"
        )
        data = self.cur.fetchall()
        for row in data:
            link, channel_id = row
            channel_info = self.get_channel_info(link)
            if channel_info["channel_id"] == channel_id:
                self.cur.execute(
                    "UPDATE channel SET title=%s, description=%s, playlist=%s, last_video=%s WHERE channel_id=%s",
                    (
                        channel_info["title"],
                        channel_info["description"],
                        channel_info["playlist"],
                        channel_info["last_video"],
                        channel_id,
                    ),
                )
                self.con.commit()
                logging.info("تم تحديث البيانات للقناة %s", channel_info["title"])

    def get_subscriber_count(self, channel_id: str) -> int:
        url = f"https://www.youtube.com/channel/{channel_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36"
        }
        cookie = {"CONSENT": "YES+cb.20210328-17-p0.en+FX+999"}
        r = requests.get(url, headers=headers, cookies=cookie, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")
        subscriber_count = soup.find("yt-formatted-string", {"id": "subscriber-count"}).text.strip()
        return int(subscriber_count.replace(",", ""))

    def remove_old_channels(self, days: int) -> int:
        self.cur.execute(
            "DELETE FROM channel WHERE channel_id NOT IN (SELECT channel_id FROM subscribe) AND last_video < DATE_SUB(NOW(), INTERVAL %s DAY)",
            (days,),
        )
        self.con.commit()
        deleted_rows = self.cur.rowcount
        logging.info("تم حذف %s قناة قديمة", deleted_rows)
        return deleted_rows
