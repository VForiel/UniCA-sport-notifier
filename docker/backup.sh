#!/bin/sh
# Sauvegarde quotidienne de PostgreSQL : un dump compressé par jour dans /backups,
# conservé BACKUP_KEEP_DAYS jours. Vérifie toutes les heures, donc rattrape un jour manqué après un redémarrage.
set -eu
umask 077
KEEP_DAYS="${BACKUP_KEEP_DAYS:-30}"

while true; do
  file="/backups/unica-db-$(date +%F).sql.gz"
  if [ ! -s "$file" ]; then
    if pg_dump --no-owner --no-privileges | gzip > "$file.tmp" && gzip -t "$file.tmp"; then
      mv "$file.tmp" "$file"
      echo "$(date '+%F %T') Sauvegarde écrite : $file ($(du -h "$file" | cut -f1))"
    else
      rm -f "$file.tmp"
      echo "$(date '+%F %T') Échec de la sauvegarde" >&2
    fi
    find /backups -name 'unica-db-*.sql.gz' -mtime +"$KEEP_DAYS" -delete
  fi
  sleep 3600
done
