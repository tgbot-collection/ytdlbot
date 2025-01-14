FROM python:3.12-alpine AS pybuilder
ADD pyproject.toml pdm.lock /build/
WORKDIR /build
RUN apk add alpine-sdk python3-dev musl-dev linux-headers
RUN pip install pdm
RUN pdm install

FROM python:3.12-alpine AS runner
WORKDIR /app

RUN apk update && apk add --no-cache ffmpeg aria2
COPY --from=pybuilder /build/.venv/lib/ /usr/local/lib/
COPY src /app
WORKDIR /app

CMD ["python" ,"main.py"]
