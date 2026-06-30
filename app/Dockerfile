# Lab 09 — App mínima en container.
# Una imagen es app + runtime + deps, todo congelado.
# Build:  docker build -t lab-09-app app/
# Run:    docker run --rm --network host -e BUCKET=lab-09-app-bucket lab-09-app

FROM python:3.12-slim

WORKDIR /app

# Capa cacheable: deps primero, código después
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# No root (mejor higiene de container)
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

ENTRYPOINT ["python", "app.py"]
