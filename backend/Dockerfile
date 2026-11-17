FROM python:3.12-slim

WORKDIR /app

# Install system runtime & build dependencies for psycopg/asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application and migration files
COPY alembic.ini .
COPY migrations ./migrations
COPY app ./app
COPY entrypoint.sh .

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PORT=8000

CMD ["./entrypoint.sh"]
