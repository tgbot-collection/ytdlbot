FROM python:alpine as builder

RUN apk update && apk add  --no-cache tzdata alpine-sdk libffi-dev ca-certificates
ADD requirements.txt /tmp/
RUN pip3 install --user -r /tmp/requirements.txt && rm /tmp/requirements.txt


FROM python:alpine
WORKDIR /ytdlbot
ENV TZ=Asia/Shanghai

RUN apk update && apk add  --no-cache ffmpeg vnstat
COPY --from=builder /root/.local /usr/local
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /usr/share/zoneinfo /usr/share/zoneinfo
COPY . /ytdlbot
RUN echo "/usr/sbin/vnstatd -d;/usr/local/bin/python ytdl.py"> /ytdlbot/start.sh

CMD ["sh", "start.sh"]