# ---- Этап 1: сборка зависимостей ----
FROM python:3.11-slim AS builder

WORKDIR /app

# Установка системных зависимостей, необходимых для компиляции некоторых пакетов (например, psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл с зависимостями Python
COPY requirements.txt .
RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Устанавливаем пакеты в директорию пользователя (для последующего копирования)
RUN pip install --no-cache-dir -r requirements.txt

# ---- Этап 2: финальный образ ----
FROM python:3.11-slim

WORKDIR /app

# Устанавливаем только runtime-зависимости (libpq для psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Копируем venv из предыдущего этапа
COPY --from=builder /app/venv /app/venv
ENV PATH="/app/venv/bin:$PATH"    

# Копируем исходный код приложения
COPY src/search/ src/search/
# COPY init_db_v2.py .
# COPY load_data_v2.py .
# COPY .csv/ .csv/

# порт, который слушает Flask (по умолчанию 5000)
EXPOSE 5000

# Запуск приложения (рекомендуется использовать gunicorn для production)
CMD ["gunicorn", "-b", "0.0.0.0:5000", "src.search.app_v2:app"]