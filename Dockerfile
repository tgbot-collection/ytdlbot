FROM python:alpine as builder

RUN apk update && apk add  --no-cache tzdata ca-certificates
ADD requirements.txt /tmp/
RUN pip3 install  -r /tmp/requirements.txt && rm /tmp/requirements.txt
COPY . /ytdl-bot

WORKDIR /ytdl-bot
ENV TZ=Asia/Shanghai
CMD ["python", "bot.py"]