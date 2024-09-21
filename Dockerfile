FROM python:3.12 as builder
ADD requirements.txt /tmp/
RUN apt update && apt install -y git && pip3 install --user -r /tmp/requirements.txt && rm /tmp/requirements.txt


FROM python:3.12-slim
WORKDIR /ytdlbot/ytdlbot
ENV TZ=Europe/London

RUN apt update && apt install -y --no-install-recommends --no-install-suggests ffmpeg vnstat git aria2
COPY --from=builder /root/.local /usr/local
COPY . /ytdlbot

CMD ["python", "-c" ,"ytdl_bpt.py"]
