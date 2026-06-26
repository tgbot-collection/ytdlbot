#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - http_client.py
# HTTP client with Cloudflare bypass support using ai-cloudscraper

__author__ = "yeshua-aguilar"

import logging
from typing import Optional

import cloudscraper
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class BypassHTTPClient:
    """HTTP client that automatically bypasses Cloudflare protection."""

    def __init__(self, bypass_enabled: bool = True, timeout: int = 30):
        self._bypass_enabled = bypass_enabled
        self._timeout = timeout
        self._session: Optional[requests.Session] = None
        self._scraper: Optional[cloudscraper.CloudScraper] = None

        self._user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )

        self._headers = {
            "User-Agent": self._user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def _create_scraper(self) -> cloudscraper.CloudScraper:
        scraper = cloudscraper.create_scraper(
            browser={
                "browser": "chrome",
                "platform": "windows",
                "desktop": True,
            },
            delay=10,
        )
        scraper.headers.update(self._headers)
        return scraper

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update(self._headers)

        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def get(self, url: str, **kwargs) -> requests.Response:
        """Make a GET request with Cloudflare bypass if needed."""
        kwargs.setdefault("timeout", self._timeout)

        if self._bypass_enabled:
            return self._bypass_get(url, **kwargs)
        return self._normal_get(url, **kwargs)

    def _bypass_get(self, url: str, **kwargs) -> requests.Response:
        """Try Cloudflare bypass first, fallback to normal request."""
        try:
            if self._scraper is None:
                self._scraper = self._create_scraper()

            logging.debug("Attempting Cloudflare bypass for %s", url)
            response = self._scraper.get(url, **kwargs)
            
            if response.status_code == 403 and "cloudflare" in response.text.lower():
                logging.warning("Cloudflare bypass failed, trying normal request")
                return self._normal_get(url, **kwargs)
            
            return response
        except Exception as e:
            logging.warning("Cloudflare bypass error: %s, falling back to normal request", e)
            return self._normal_get(url, **kwargs)

    def _normal_get(self, url: str, **kwargs) -> requests.Response:
        """Make a normal GET request without bypass."""
        if self._session is None:
            self._session = self._create_session()

        return self._session.get(url, **kwargs)

    def close(self):
        """Close all sessions."""
        if self._session:
            self._session.close()
            self._session = None
        if self._scraper:
            self._scraper.close()
            self._scraper = None


_client_instance: Optional[BypassHTTPClient] = None


def get_http_client(bypass_enabled: bool = True) -> BypassHTTPClient:
    """Get or create a shared HTTP client instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = BypassHTTPClient(bypass_enabled=bypass_enabled)
    return _client_instance


def get_cloudflare_bypass_session() -> cloudscraper.CloudScraper:
    """Get a CloudScraper session for yt-dlp or other libraries."""
    scraper = cloudscraper.create_scraper(
        browser={
            "browser": "chrome",
            "platform": "windows",
            "desktop": True,
        },
        delay=10,
    )
    return scraper


def get_realistic_headers() -> dict:
    """Get realistic browser headers for manual use."""
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }
