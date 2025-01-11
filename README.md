# ytdlbot

[![docker image](https://github.com/tgbot-collection/ytdlbot/actions/workflows/builder.yaml/badge.svg)](https://github.com/tgbot-collection/ytdlbot/actions/workflows/builder.yaml)

**YouTube Download Bot🚀🎬⬇️**

This Telegram bot allows you to download videos from YouTube and [other supported websites](#supported-websites).

# Usage

* EU🇪🇺: [https://t.me/benny_2ytdlbot](https://t.me/benny_2ytdlbot)
* Singapore🇸🇬:[https://t.me/benny_ytdlbot](https://t.me/benny_ytdlbot)

* Join Telegram Channel https://t.me/+OGRC8tp9-U9mZDZl for updates.

Just send a link directly to the bot.

# Supported websites

* YouTube 😅
* Any websites [supported by yt-dlp](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)

  ### Specific link downloader (Use /spdl for these links)
    * Instagram (Videos, Photos, Reels, IGTV & carousel)
    * Pixeldrain
    * KrakenFiles
    * Terabox (file/~~folders~~) (you need to add cookies txt in ytdlbot folder with name) 
    [terabox.txt](https://github.com/ytdl-org/youtube-dl#how-do-i-pass-cookies-to-youtube-dl).

# Features
1. fast download and upload.
2. ads free
3. support progress bar
4. audio conversion
5. different video resolutions
6. sending as file or streaming as video
7. cache mechanism - download once for the same video.
8. Supports multiple download engines (yt-dlp, aria2, requests).

 
> ## Limitations
> Due to limitations on servers and bandwidth, there are some restrictions on this free service.
> * Each user is limited to 5 free downloads per 24-hour period
 
  
# Screenshots

## Normal download

![](assets/1.jpeg)

## Instagram download

![](assets/instagram.png)

![](assets/2.jpeg)

# How to deploy?

This bot can be deployed on any platform that supports Python.

## Run natively on your machine
* use pdm
* pdm install
* copy .env.example to .env
* python main.py
 
 
## Docker

One line command to run the bot

```shell
docker run -e APP_ID=111 -e APP_HASH=111 -e TOKEN=370FXI bennythink/ytdlbot
```

# Complete deployment guide for docker-compose

 
# Command

```
start - Let's start
about - What's this bot?
help - Help
spdl - Use to download specific link downloader links
ytdl - Download video in group
aria2 - Download file using aria2
settings - Set your preference
unsub - Unsubscribe from YouTube Channel
ping - Ping the Bot
```

# Test data
<details><summary>Tap to expand</summary>

## Test video

https://www.youtube.com/watch?v=V3RtA-1b_2E

## Test Playlist

https://www.youtube.com/playlist?list=PL1Hdq7xjQCJxQnGc05gS4wzHWccvEJy0w

## Test twitter

https://twitter.com/nitori_sayaka/status/1526199729864200192
https://twitter.com/BennyThinks/status/1475836588542341124

## Test instagram

* single image: https://www.instagram.com/p/CXpxSyOrWCA/
* single video: https://www.instagram.com/p/Cah_7gnDVUW/
* reels: https://www.instagram.com/p/C0ozGsjtY0W/
* image carousel: https://www.instagram.com/p/C0ozPQ5o536/
* video and image carousel: https://www.instagram.com/p/C0ozhsVo-m8/

## Test Pixeldrain

https://pixeldrain.com/u/765ijw9i

## Test KrakenFiles

https://krakenfiles.com/view/oqmSTF0T5t/file.html

## Test TeraBox

https://terabox.com/s/1mpgNshrZVl6KuH717Hs23Q

</details>

# Donation

Found this bot useful? You can donate to support the development of this bot.

## Donation Platforms

* [Buy me a coffee](https://www.buymeacoffee.com/bennythink)
* [GitHub Sponsor](https://github.com/sponsors/BennyThink)

## Stripe

You can choose to donate via Stripe.

| USD(Card, Apple Pay and Google Pay)              | CNY(Card, Apple Pay, Google Pay and Alipay)      |
|--------------------------------------------------|--------------------------------------------------|
| [USD](https://buy.stripe.com/cN203sdZB98RevC3cd) | [CNY](https://buy.stripe.com/dR67vU4p13Ox73a6oq) |
| ![](assets/USD.png)                              | ![](assets/CNY.png)                              |

## Cryptocurrency

TRX or USDT(TRC20)

![](assets/tron.png)

```
TF9peZjC2FYjU4xNMPg3uP4caYLJxtXeJS
```

# License

Apache License 2.0
