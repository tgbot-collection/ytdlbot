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
	git tag -a v$(shell date "+%Y-%m-%d") -m v$(shell date "+%Y-%m-%d")
	git push --tags