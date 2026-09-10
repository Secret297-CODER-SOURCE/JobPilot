# JobPilot — веб-приложение поиска работы (Flask + WebSocket + Playwright).
#
# Файл лежит в jobscraper/, но контекст сборки — родительская папка (там же
# webapp.py, db.py, static/, templates/), поэтому собирать так:
#   docker build -f jobscraper/Dockerfile -t jobpilot ..    (из jobscraper/)
# Проще всего — через docker-compose (context/dockerfile уже настроены):
#   cd jobscraper && docker compose up -d --build

FROM python:3.12-slim

WORKDIR /app

# curl нужен только для healthcheck в docker-compose
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY jobscraper/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --with-deps сам подтягивает системные библиотеки, нужные Chromium на Debian
RUN playwright install --with-deps chromium

COPY . .

# Данные (SQLite, загруженные файлы, ключ сессии) — в отдельном томе,
# чтобы пересборка образа их не стирала. См. db.py/webapp.py: без переменной
# поведение как раньше (данные рядом с кодом), с ней — в /app/data.
ENV JOBPILOT_DATA_DIR=/app/data
# 127.0.0.1 внутри контейнера недоступен снаружи — трафик с проброшенного
# порта приходит через bridge-интерфейс, а не loopback
ENV JOBPILOT_HOST=0.0.0.0
RUN mkdir -p /app/data

EXPOSE 5057

CMD ["python", "webapp.py"]
