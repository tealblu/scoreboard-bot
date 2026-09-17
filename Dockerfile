FROM python:3.12.12-slim-trixie

WORKDIR /bot
COPY . /bot

RUN python -m pip install -r requirements.txt

ENTRYPOINT [ "python", "bot.py" ]