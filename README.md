# ytdlbot

[![docker image](https://github.com/tgbot-collection/ytdlbot/actions/workflows/builder.yaml/badge.svg)](https://github.com/tgbot-collection/ytdlbot/actions/workflows/builder.yaml)

YouTube Download Bot🚀

This Telegram bot allows you to download videos from YouTube and other supported platforms, including Instagram!

-----
**READ [FAQ](FAQ.md) FIRST IF YOU ENCOUNTER ANY ISSUES.**

-----
<details> <summary>Deploy to heroku</summary>

<a href="https://heroku.com/deploy"><img src="https://www.herokucdn.com/deploy/button.svg" alt="Deploy to Heroku"></a>

If you are having trouble deploying, you can fork the project to your personal account and deploy it from there.

**Starting November 28, 2022, free Heroku Dynos, free Heroku Postgres, and free Heroku Data for Redis® plans will no
longer be available.**
[Heroku Announcement](https://devcenter.heroku.com/articles/free-dyno-hours)
</details>

# Usage

[https://t.me/benny_ytdlbot](https://t.me/benny_ytdlbot)

Send link directly to the bot. Any
Websites [supported by youtube-dl](https://ytdl-org.github.io/youtube-dl/supportedsites.html) will work to.

# Limitations of my bot

Due to limitations on servers and bandwidth, there are some restrictions on this free service.

* Each user is limited to 20 free downloads per 24-hour period
* there is a maximum of three subscriptions allowed for YouTube channels.

If you need more downloads, you can purchase additional tokens. Additionally, you have the option of deploying your
own bot. See below instructions.

# Features

1. fast download and upload.
2. ads free
3. support progress bar
4. audio conversion
5. playlist support
6. payment support
7. support different video resolutions
8. support sending as file or streaming as video
9. supports celery worker distribution - faster than before.
10. subscriptions to YouTube Channels
11. cache mechanism - download once for the same video.
12. support instagram posts

# Screenshots

## Normal download

![](assets/1.jpeg)

## Instagram download

![](assets/instagram.png)

## celery

![](assets/2.jpeg)

# How to deploy?

This bot can be deployed on any platform that supports Python.

Need help with deployment or exclusive features? I offer paid service - contact me at @BennyThink

## Run natively on your machine

To deploy this bot, follow these steps:

1. Clone the code from the repository.
2. Install FFmpeg.
3. Install Python 3.6 or a later version.
4. Install Aria2 and add it to the PATH.
5. Install the required packages by running `pip3 install -r requirements.txt`.
6. Set the environment variables `TOKEN`, `APP_ID`, `APP_HASH`, and any others that you may need.
7. Run `python3 ytdl_bot.py`.

## Docker

This bot has a simple one-line code and some functions, such as VIP and ping, are disabled.

```shell
docker run -e APP_ID=111 -e APP_HASH=111 -e TOKEN=370FXI bennythink/ytdlbot
```

# Complete deployment guide for docker-compose

* contains every functionality
* compatible with amd64, arm64 and armv7l

## 1. get docker-compose.yml

Download `docker-compose.yml` file to a directory

## 2. create data directory

```shell
mkdir data
mkdir env
```

## 3. configuration

### 3.1. set environment variables

```shell
vim env/ytdl.env
```

You can configure all the following environment variables:

* WORKERS: workers count for celery
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
* ENABLE_CELERY: celery mode, default: disable
* ENABLE_QUEUE: celery queue
* BROKER: celery broker, should be redis://redis:6379/0
* MYSQL_HOST:MySQL host
* MYSQL_USER: MySQL username
* MYSQL_PASS: MySQL password
* AUDIO_FORMAT: default audio format
* ARCHIVE_ID: forward all downloads to this group/channel
* IPv6 = os.getenv("IPv6", False)
* ENABLE_FFMPEG = os.getenv("ENABLE_FFMPEG", False)
* PROVIDER_TOKEN: stripe token on Telegram payment
* PLAYLIST_SUPPORT: download playlist support
* ENABLE_ARIA2: enable aria2c download
* FREE_DOWNLOAD: free download count per day
* TOKEN_PRICE: token price per 1 USD
* GOOGLE_API_KEY: YouTube API key, required for YouTube video subscription.

## 3.2 Set up init data

If you only need basic functionality, you can skip this step.

### 3.2.1 Create MySQL db

Required for VIP, settings, YouTube subscription.

```shell
docker-compose up -d
docker-compose exec mysql bash

mysql -u root -p

> create database ytdl;
```

### 3.2.2 Setup flower db in `ytdlbot/ytdlbot/data`

Required if you enable celery and want to monitor the workers.

```shell
{} ~ python3
Python 3.9.9 (main, Nov 21 2021, 03:22:47)
[Clang 12.0.0 (clang-1200.0.32.29)] on darwin
Type "help", "copyright", "credits" or "license" for more information.
>>> import dbm;dbm.open("flower","n");exit()
```

### 3.2.3 Setup instagram cookies

You don't need to do this anymore! This bot support instagram posts out of the box, including photos, videos and reels.

## 3.3 Tidy docker-compose.yml

In `flower` service section, you may want to change your basic authentication username password and publish port.

You can also limit CPU and RAM usage by adding a `deploy' key:

```docker
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 1500M
```

Be sure to use `--compatibility` when deploying.

## 4. run

### 4.1. standalone mode

If you only want to run the mode without any celery worker and VIP mode, you can just start `ytdl` service

```shell
docker-compose up -d ytdl
```

### 4.2 VIP mode

You'll have to start MySQL and redis to support VIP mode, subscription and settings.

```
docker-compose up -d mysql redis ytdl
```

### 4.3 Celery worker mode

Firstly, set `ENABLE_CELERY` to true. And then, on one machine:

```shell
docker-compose up -d
```

On the other machine:

```shell
docker-compose -f worker.yml up -d
```

**⚠️ Please bear in mind that you should not publish Redis directly on the internet.
Instead, you can use WireGuard to wrap it up for added security.**

## kubernetes

refer guide here [kubernetes](k8s.md)

# Command

```
start - Let's start
about - What's this bot?
ping - Bot running status
help - Help
ytdl - Download video in group
settings - Set your preference
buy - Buy token
direct - Download file directly
sub - Subscribe to YouTube Channel
unsub - Unsubscribe from YouTube Channel
sub_count - Check subscription status, owner only.
uncache - Delete cache for this link, owner only.
purge - Delete all tasks, owner only.
```

# Test data

## Test video

https://www.youtube.com/watch?v=BaW_jenozKc

## Test Playlist

https://www.youtube.com/playlist?list=PL1Hdq7xjQCJxQnGc05gS4wzHWccvEJy0w

## Test twitter

https://twitter.com/nitori_sayaka/status/1526199729864200192
https://twitter.com/BennyThinks/status/1475836588542341124

## Test instagram

https://www.instagram.com/p/ClBSqo3PkJw/

https://www.instagram.com/p/CaiAHoWDnrM/

https://www.instagram.com/p/CZtUDyyv1u1/

# Donation

* [Buy me a coffee](https://www.buymeacoffee.com/bennythink)
* [Afdian](https://afdian.net/@BennyThink)
* [GitHub Sponsor](https://github.com/sponsors/BennyThink)

## Stripe

You can choose to donate via Stripe by clicking the button below.

Select the currency and payment method that suits you.

| USD(Card, Apple Pay and Google Pay)              | SEK(Card, Apple Pay and Google Pay)              | CNY(Card, Apple Pay, Google Pay and Alipay)      |
|--------------------------------------------------|--------------------------------------------------|--------------------------------------------------|
| [USD](https://buy.stripe.com/cN203sdZB98RevC3cd) | [SEK](https://buy.stripe.com/bIYbMa9JletbevCaEE) | [CNY](https://buy.stripe.com/dR67vU4p13Ox73a6oq) |
| ![](assets/USD.png)                              | ![](assets/SEK.png)                              | ![](assets/CNY.png)                              |

# License

Apache License 2.0
