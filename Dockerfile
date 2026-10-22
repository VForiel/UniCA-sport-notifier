FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Dépendances système pour psycopg, cryptography et les navigateurs Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Installation des dépendances Python
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Installation du navigateur Chromium headless pour Playwright et de ses dépendances système
RUN playwright install --with-deps chromium

# Copie du code source
COPY . .

# Droits d'exécution sur le script d'entrée ; utilisateur non privilégié qui ne peut écrire
# que dans les dossiers de fichiers statiques et de médias (le code reste à root, en lecture seule)
RUN chmod +x /app/docker/entrypoint.sh &&     useradd --create-home --uid 1000 app &&     mkdir -p /app/staticfiles /app/media &&     chown app:app /app/staticfiles /app/media

USER app

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
