define NOLOGGING

    logging:
      driver: none
endef
export NOLOGGING

default:
	docker pull bennythink/ytdlbot

bot:
	make
	docker-compose up -d
	docker system prune -a --volumes -f

worker:
	make
	docker-compose -f worker.yml up -d
	docker system prune -a --volumes -f
	sleep 5

weak-worker:
	make
	docker-compose --compatibility -f worker.yml up -d
	docker system prune -a --volumes -f
	sleep 5

upgrade-all-worker:
	bash upgrade_worker.sh

tag:
	git tag -a v$(shell date "+%Y-%m-%d")_$(shell git rev-parse --short HEAD) -m v$(shell date "+%Y-%m-%d")
	git push --tags

nolog:
	echo "$$NOLOGGING">> worker.yml

flower:
	echo  'import dbm;dbm.open("data/flower","n");exit()'| python3

up:
	docker build -t bennythink/ytdlbot:latest .
	docker-compose -f docker-compose.yml -f worker.yml up -d

ps:
	docker-compose -f docker-compose.yml -f worker.yml ps

down:
	docker-compose -f docker-compose.yml -f worker.yml down

logs:
	docker-compose -f docker-compose.yml -f worker.yml logs -f worker ytdl