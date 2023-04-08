docker run -d --restart unless-stopped --name ytdl \
   --net host \
     -e TOKEN=12345 \
     -e APP_ID=123123 \
     -e APP_HASH=4990 \
     -e ENABLE_CELERY=True \
     -e REDIS=192.168.6.1 \
     -e MYSQL_HOST=192.168.6.1 \
     -e WORKERS=4 \
     -e VIP=True \
     -e CUSTOM_TEXT=#StandWithUkraine \
     bennythink/ytdlbot \
     /usr/local/bin/supervisord -c "/ytdlbot/conf/supervisor_worker.conf"
