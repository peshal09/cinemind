# API image for CineMind.
FROM python:3.11-slim

# Predictable, log-friendly Python in containers.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install deps first so this layer is cached unless requirements.txt changes.
# psycopg2-binary ships wheels, so no system build toolchain is needed.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code (and the bundled MovieLens CSVs, so the seed needs no network).
COPY . .

EXPOSE 8000

# Seed the DB (idempotent) then start the server.
ENTRYPOINT ["./docker/entrypoint.sh"]
