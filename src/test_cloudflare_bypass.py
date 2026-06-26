#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - test_cloudflare_bypass.py
# Test script for Cloudflare bypass functionality using ai-cloudscraper

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.http_client import BypassHTTPClient, get_realistic_headers


def test_cloudflare_bypass():
    print("=" * 50)
    print("Testing Cloudflare Bypass (ai-cloudscraper)")
    print("=" * 50)
    
    test_sites = [
        ("https://nowsecure.nl/", "NowSecure (Cloudflare protected)"),
        ("https://www.google.com/", "Google (no protection)"),
    ]
    
    client = BypassHTTPClient(bypass_enabled=True)
    
    for url, description in test_sites:
        print(f"\nTesting: {description}")
        print(f"URL: {url}")
        
        try:
            resp = client.get(url, timeout=10)
            print(f"Status: {resp.status_code}")
            print(f"Content length: {len(resp.text)} chars")
            print("Result: OK")
        except Exception as e:
            print(f"Error: {e}")
            print("Result: FAILED")
    
    client.close()
    print("\n" + "=" * 50)
    print("Test completed!")
    print("=" * 50)


def test_headers():
    print("\n" + "=" * 50)
    print("Testing Realistic Headers")
    print("=" * 50)
    
    headers = get_realistic_headers()
    
    for key, value in headers.items():
        print(f"{key}: {value}")
    
    print("\nResult: OK")


def test_direct_download_usage():
    print("\n" + "=" * 50)
    print("Testing DirectDownload Usage Pattern")
    print("=" * 50)
    
    from utils.http_client import get_http_client
    
    client = get_http_client(bypass_enabled=True)
    
    print("\nTesting single instance pattern:")
    print(f"Client type: {type(client).__name__}")
    
    try:
        resp = client.get("https://httpbin.org/headers", timeout=5)
        print(f"Status: {resp.status_code}")
        print("Result: OK")
    except Exception as e:
        print(f"Error: {e}")
        print("Result: FAILED")
    
    print("\n" + "=" * 50)


if __name__ == "__main__":
    test_cloudflare_bypass()
    test_headers()
    test_direct_download_usage()
