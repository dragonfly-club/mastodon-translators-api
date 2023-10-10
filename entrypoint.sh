#!/bin/bash
nohup redis-server /etc/redis/redis.conf > /dev/null &
sudo -Eu mastodon uwsgi --ini uwsgi.ini