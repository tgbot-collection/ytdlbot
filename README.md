# ytdlbot

[![docker image](https://github.com/tgbot-collection/ytdlbot/actions/workflows/builder.yaml/badge.svg)](https://github.com/tgbot-collection/ytdlbot/actions/workflows/builder.yaml)

**YouTube Download Bot🚀🎬⬇️**

This Telegram bot allows you to download videos from YouTube and [other supported websites](#supported-websites).


# Usage

* EU(recommended): [https://t.me/benny_2ytdlbot](https://t.me/benny_2ytdlbot)
* Asia:[https://t.me/benny_ytdlbot](https://t.me/benny_ytdlbot)

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
5. playlist download
6. payment support: afdian, buy me a coffee, Telegram Payment and Tron(TRX)
7. different video resolutions
8. sending as file or streaming as video
10. subscriptions to YouTube Channels
11. cache mechanism - download once for the same video.
12. instagram posts(only available for my bot)
13. 4 GiB file size support with Telegram Premium
14. History and inline mode support
15. Supports multiple download engines (yt-dlp, aria2, requests).

> [!NOTE]
> **For users of [my official bot](https://t.me/benny_ytdlbot)**\
> Files larger than 2 GiB will be automatically uploaded by me(My Premium Account). By utilizing our service for such downloads, you consent to this process. \
> That means I know who you are and what you download. \
> Rest assured that we handle your personal information with the utmost care.
>
> ## Limitations
> Due to limitations on servers and bandwidth, there are some restrictions on this free service.
> * Each user is limited to 5 free downloads per 24-hour period
> * Maximum of three subscriptions allowed for YouTube channels.
> * Files bigger than 2 GiB will require at least 1 download token.
>
> If you need more downloads, you can buy download tokens.
>
> **Thank you for using the [official bot](https://t.me/benny_ytdlbot).**

# Screenshots

## Normal download

![](assets/1.jpeg)

## Instagram download

![](assets/instagram.png)

![](assets/2.jpeg)

# How to deploy?

This bot can be deployed on any platform that supports Python.

## Run natively on your machine

To deploy this bot, follow these steps:

1. Install bot dependencies
   * Install Python 3.10 or a later version, FFmpeg.
   * (optional)Aria2 and add it to the PATH.

2. Clone the code from the repository and cd into it.
   * ```Bash
     git clone https://github.com/tgbot-collection/ytdlbot
     ```
   * ```Bash
     cd ytdlbot/
     ```
3. Creating a virtual environment and installing required modules in Python.
   * ```Python
     python -m venv venv
     ```
   * ```Bash
     source venv/bin/activate   # Linux
     #or
     .\venv\Scripts\activate   # Windows
     ```
   * ```Python
     pip install --upgrade pip
     ```
   * ```Python
     pip install -r requirements.txt
     ```
4. Set the environment variables `TOKEN`, `APP_ID`, `APP_HASH`, and any others that you may need.
   * Change values in ytdlbot/config.py or
   * Use export APP_ID=111 APP_HASH=111 TOKEN=123
5. Finally, run the bot with
   * ```Python
     python ytdlbot/ytdl_bot.py
     ```

## Docker

One line command to run the bot

```shell
docker run -e APP_ID=111 -e APP_HASH=111 -e TOKEN=370FXI bennythink/ytdlbot
```

# Complete deployment guide for docker-compose

* contains every functionality
* compatible with amd64 and arm64

## 1. get docker-compose.yml

Download `docker-compose.yml` file to a directory

You can configure all the following environment variables:

* PYRO_WORKERS: number of workers for pyrogram, default is 100
* APP_ID: **REQUIRED**, get it from https://core.telegram.org/
* APP_HASH: **REQUIRED**
* TOKEN: **REQUIRED**
* REDIS: **REQUIRED if you need VIP mode and cache** ⚠️ Don't publish your redis server on the internet. ⚠️
* EXPIRE: token expire time, default: 1 day
* ENABLE_VIP: enable VIP mode
* OWNER: owner username
* AUTHORIZED_USER: only authorized users can use the bot
* REQUIRED_MEMBERSHIP: group or channel username, user must join this group to use the bot
* MYSQL_HOST:MySQL host
* MYSQL_USER: MySQL username
* MYSQL_PASS: MySQL password
* AUDIO_FORMAT: default audio format
* ARCHIVE_ID: forward all downloads to this group/channel
* IPv6 = os.getenv("IPv6", False)
* ENABLE_FFMPEG = os.getenv("ENABLE_FFMPEG", False)
* PROVIDER_TOKEN: stripe token on Telegram payment
* PLAYLIST_SUPPORT: download playlist support
* M3U8_SUPPORT: download m3u8 files support
* ENABLE_ARIA2: enable aria2c download
* FREE_DOWNLOAD: free download count per day
* TOKEN_PRICE: token price per 1 USD
* GOOGLE_API_KEY: YouTube API key, required for YouTube video subscription.
* RCLONE_PATH: rclone path to upload files to cloud storage
* TMPFILE_PATH: tmpfile path(file download path)
* TRONGRID_KEY: TronGrid key, better use your own key to avoid rate limit
* TRON_MNEMONIC: Tron mnemonic, the default one is on nile testnet.
* PREMIUM_USER: premium user ID, it can help you to download files larger than 2 GiB

### 3.2.1 Create MySQL db

Required for VIP(Download token), settings, YouTube subscription.

```shell
docker-compose up -d
docker-compose exec mysql bash

mysql -u root -p

> create database ytdl;
```

## 3.3 Tidy docker-compose.yml

You can also limit CPU and RAM usage by adding a `deploy` key, use `--compatibility` when deploying.

```docker
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 1500M
```

```shell
docker-compose up -d ytdl
```

### 4.2 VIP mode

You'll have to start MySQL and redis to support VIP mode, subscription and settings.

```
docker-compose up -d mysql redis ytdl
```

```shell
docker-compose -f worker.yml up -d
```

**⚠️ You should not publish Redis directly on the internet. ⚠️**

### 4.4 4 GiB Support

1. Subscribe to Telegram Premium
2. Setup user id `PREMIUM_USER` in `ytdl.env`
3. Create session file by running `python premium.py`
4. Copy the session file `premium.session` to `data` directory
5. `docker-compose up -d premium`

# Command

```
start - Let's start
about - What's this bot?
help - Help
spdl - Use to download specific link downloader links
ytdl - Download video in group
leech - Download file using aria2
direct - Download file using requests
settings - Set your preference
buy - Buy token
sub - Subscribe to YouTube Channel
unsub - Unsubscribe from YouTube Channel
sub_count - Check subscription status, owner only.
uncache - Delete cache for this link, owner only.
purge - Delete all tasks, owner only.
ping - Ping the Bot
stats - Bot running status
show_history - Show download history
clear_history - Clear download history
```

# Test data
<details><summary>Tap to expand</summary>

## Test video

https://www.youtube.com/watch?v=BaW_jenozKc

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
