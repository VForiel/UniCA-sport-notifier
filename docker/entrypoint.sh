#!/bin/sh
set -e

echo "=== UniCA Sport Notifier - Démarrage du conteneur ==="

# Attente de PostgreSQL si configuré
if [ -n "$DATABASE_URL" ] && echo "$DATABASE_URL" | grep -q "postgres://"; then
  echo "Attente de la base de données PostgreSQL..."
  while ! python -c "import psycopg, os; psycopg.connect(os.environ['DATABASE_URL'])" 2>/dev/null; do
    sleep 1
  done
  echo "Base de données PostgreSQL prête."
fi

# Migrations Django idempotentes
echo "Application des migrations Django..."
python manage.py migrate --noinput

# Collecte des fichiers statiques
echo "Collecte des fichiers statiques..."
python manage.py collectstatic --noinput

# Création du superadmin par défaut si inexistant
echo "Vérification / Initialisation du superadministrateur..."
python manage.py create_default_superuser

echo "Démarrage du processus principal : $@"
exec "$@"
