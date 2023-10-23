FROM python:3.11
WORKDIR /app

COPY ./requirements.txt ./
RUN pip install -r requirements.txt 
RUN apt update && apt install redis nodejs sudo -y

COPY ./app.py .
COPY ./entrypoint.sh .
COPY ./uwsgi.ini .

ARG UID=1000

RUN useradd -u $UID mastodon --no-create-home
RUN chown mastodon:mastodon .

ENTRYPOINT ["bash", "./entrypoint.sh"]