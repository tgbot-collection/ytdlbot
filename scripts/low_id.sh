#!/bin/bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin:/usr/local/go/bin:/opt/bin

# Check the logs for the given string
if docker-compose logs --tail=100 ytdl | grep -q "The msg_id is too low"; then
    # If the string is found, stop the ytdl service
    echo "ytdl service stopped due to 'The msg_id is too low' found in logs."
    docker-compose stop ytdl && docker-compose rm ytdl && docker-compose up -d

else
    echo "String not found in logs."
fi
