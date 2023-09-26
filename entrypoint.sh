#!/bin/bash
nohup redis-server /etc/redis/redis.conf > /dev/null &
sudo -u mastodon uwsgi --ini uwsgi.ini