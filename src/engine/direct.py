#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - direct.py

import logging
import os
import re
import pathlib
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

import filetype
import requests

from config import ENABLE_ARIA2, TMPFILE_PATH, PROXY
from engine.base import BaseDownloader


class DirectDownload(BaseDownloader):

    def _setup_formats(self) -> list | None:
        # direct download doesn't need to setup formats
        pass

    # def _get_aria2_name(self):
    #     try:
    #         cmd = f"aria2c --truncate-console-readout=true -x10 --dry-run --file-allocation=none {self._url}"
    #         result = subprocess.run(cmd, stdout=subprocess.PIPE, shell=True)
    #         stdout_str = result.stdout.decode("utf-8")
    #         name = os.path.basename(stdout_str).split("\n")[0]
    #         if len(name) == 0:
    #             name = os.path.basename(self._url)
    #         return name
    #     except Exception:
    #         name = os.path.basename(self._url)
    #         return name

    def _requests_download(self):
        logging.info("Requests download with url %s", self._url)
        proxies = {"http": PROXY, "https": PROXY} if PROXY else None
        response = requests.get(self._url, stream=True, proxies=proxies)
        response.raise_for_status()
        file = Path(self._tempdir.name).joinpath(uuid4().hex)
        with open(file, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        ext = filetype.guess_extension(file)
        if ext is not None:
            new_name = file.with_suffix(f".{ext}")
            file.rename(new_name)

        return [file.as_posix()]

    def _aria2_download(self):
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        # filename = self._get_aria2_name()
        self._process = None
        try:
            self._bot_msg.edit_text("Aria2 download starting...")
            temp_dir = self._tempdir.name
            command = [
                "aria2c",
                "--max-tries=3",
                "--max-concurrent-downloads=8",
                "--max-connection-per-server=16",
                "--split=16",
                "--summary-interval=1",
                "--console-log-level=notice",
                "--show-console-readout=true",
                "--quiet=false",
                "--human-readable=true",
                f"--user-agent={ua}",
                "-d", temp_dir,
                self._url,
            ]
            # add proxy if configured
            if PROXY:
                command.extend(["--all-proxy", PROXY])

            self._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )

            while True:
                line = self._process.stdout.readline()
                if not line:
                    if self._process.poll() is not None:
                        break
                    continue

                progress = self.__parse_progress(line)
                if progress:
                    self.download_hook(progress)
                elif "Download complete:" in line:
                    self.download_hook({"status": "complete"})

            self._process.wait(timeout=300)
            success = self._process.wait() == 0
            if not success:
                raise subprocess.CalledProcessError(
                    self._process.returncode, 
                    command, 
                    self._process.stderr.read()
                )
            if self._process.returncode != 0:
                raise subprocess.CalledProcessError(
                    self._process.returncode, 
                    command, 
                    stderr
                )

            # This will get [Path_object] if a file is found, or None if no files are found.
            files = [f] if (f := next((item for item in Path(temp_dir).glob("*") if item.is_file()), None)) is not None else None
            if files is None:
                logging.error(f"No files found in {temp_dir}")
                raise FileNotFoundError(f"No files found in {temp_dir}")
            else:
                logging.info("Successfully downloaded file: %s", files[0])

            return files

        except subprocess.TimeoutExpired:
            error_msg = "Download timed out after 5 minutes."
            logging.error(error_msg)
            self._bot_msg.edit_text(f"Download failed!❌\n\n{error_msg}")
            return []
        except Exception as e:
            self._bot_msg.edit_text(f"Download failed!❌\n\n`{e}`")
            return []
        finally:
            if self._process:
                self._process.terminate()
                self._process = None

    def __parse_progress(self, line: str) -> dict | None:
        if "Download complete:" in line or "(OK):download completed" in line:
            return {"status": "complete"}

        progress_match = re.search(
            r'\[#\w+\s+(?P<progress>[\d.]+[KMGTP]?iB)/(?P<total>[\d.]+[KMGTP]?iB)\(.*?\)\s+CN:\d+\s+DL:(?P<speed>[\d.]+[KMGTP]?iB)\s+ETA:(?P<eta>[\dhms]+)',
            line
        )

        if progress_match:
            return {
                "status": "downloading",
                "downloaded_bytes": self.__parse_size(progress_match.group("progress")),
                "total_bytes": self.__parse_size(progress_match.group("total")),
                "_speed_str": f"{progress_match.group('speed')}/s",
                "_eta_str": progress_match.group("eta")
            }

        # Fallback check for summary lines
        if "Download Progress Summary" in line and "MiB" in line:
            return {"status": "progress", "details": line}

        return None

    def __parse_size(self, size_str: str) -> int:
        units = {
            "B": 1, 
            "K": 1024, "KB": 1024, "KIB": 1024,
            "M": 1024**2, "MB": 1024**2, "MIB": 1024**2,
            "G": 1024**3, "GB": 1024**3, "GIB": 1024**3,
            "T": 1024**4, "TB": 1024**4, "TIB": 1024**4
        }
        match = re.match(r"([\d.]+)([A-Za-z]*)", size_str.replace("i", "").upper())
        if match:
            number, unit = match.groups()
            unit = unit or "B"
            return int(float(number) * units.get(unit, 1))
        return 0

    def _download(self, formats=None) -> list:
        if ENABLE_ARIA2:
            return self._aria2_download()
        return self._requests_download()

    def _start(self):
        downloaded_files = self._download()
        self._upload(files=downloaded_files)