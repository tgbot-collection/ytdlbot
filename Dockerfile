FROM python:alpine as builder

RUN apk update && apk add  --no-cache tzdata alpine-sdk libffi-dev ca-certificates
ADD requirements.txt /tmp/
RUN pip3 install --user -r /tmp/requirements.txt && rm /tmp/requirements.txt


FROM python:alpine
RUN apk update && apk add  --no-cache ffmpeg git
COPY --from=builder /root/.local /usr/local
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /usr/share/zoneinfo /usr/share/zoneinfo
COPY . /ytdl-bot
RUN cd /ytdl-bot && git submodule update --init --recursive && apk del git

WORKDIR /ytdl-bot
ENV TZ=Asia/Shanghai
CMD ["python", "ytdl.py"]