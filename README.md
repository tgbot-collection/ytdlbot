# ytdl-bot
Download videos from YouTube and other platforms through a Telegram Bot


# Usage:

[https://t.me/benny_ytdlbot](https://t.me/benny_ytdlbot)

Send link from YouTube directly to the bot. 
Any platform [supported by youtube-dl](https://ytdl-org.github.io/youtube-dl/supportedsites.html) will also work.

# How to deploy?
## Normal
1. install Python 3.6+
2. pip3 install -r requirements.txt
3. set environment variables `TOKEN`, `APP_ID` and `APP_HASH`
4. `python3 bot.py`
5. supervisor on your own preference.
## docker
see [here](https://github.com/tgbot-collection/BotsRunner)

# License
Apache License 2.0
