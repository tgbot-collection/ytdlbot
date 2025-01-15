#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - instagram.py


import pathlib
import re

import filetype
import requests
from base import BaseDownloader


class InstagramDownload(BaseDownloader):
    def extract_code(self):
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
            r"(?:https?://)?(?:www\.)?(?:threads\.net)(?:/[@\w.]+)?(?:/post)?/([\w-]+)(?:/?\?.*)?$",
        ]

        for pattern in patterns:
            match = re.search(pattern, self._url)
            if match:
                if pattern == patterns[0]:  # Check if it's the stories highlights pattern
                    # Return the URL as it is
                    return self._url
                else:
                    # Return the code part (first group)
                    return match.group(1)

        return None

    def _setup_formats(self) -> list | None:
        pass

    def _download(self, formats):
        # TODO: Implement download method
        resp = requests.get(f"http://instagram:15000/?url={self._url}").json()
        code = self.extract_code()
        counter = 1
        video_paths = []
        if url_results := resp.get("data"):
            for link in url_results:
                req = requests.get(link, stream=True)
                length = int(req.headers.get("content-length"))
                content = req.content
                ext = filetype.guess_extension(content)
                filename = f"{code}_{counter}.{ext}"
                save_path = pathlib.Path(self._tempdir, filename)
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

    def _start(self):
        pass
