FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# system deps for building native extensions commonly required by packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# install python deps (adds gunicorn for production serving)
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt gunicorn

# copy project files
COPY . .

# run as non-root for better security
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

ENV FLASK_APP=web_app.py \
    FLASK_ENV=production

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "web_app:app", "--workers", "3", "--threads", "2"]