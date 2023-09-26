FROM python:3
WORKDIR /app

COPY ./requirements.txt ./
RUN pip install -r requirements.txt 
RUN apt update && apt install redis nodejs sudo -y

COPY ./app.py .
COPY ./entrypoint.sh .
COPY ./uwsgi.ini .

RUN useradd -u 1000 mastodon --no-create-home
RUN chown mastodon:mastodon .

ENTRYPOINT ["bash", "./entrypoint.sh"]