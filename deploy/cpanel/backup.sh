#!/usr/bin/env bash
# Back up the production PostgreSQL database.
#
# deploy.sh runs this before applying migrations. For a nightly backup add a
# cPanel cron job (one line; replace CPANELUSER and the Python version):
#
#   PYTHON=/home/CPANELUSER/virtualenv/mathkangaroo/3.12/bin/python /bin/bash /home/CPANELUSER/mathkangaroo/deploy/cpanel/backup.sh
#
# Options (environment variables):
#   PYTHON=path     Python of the app's virtualenv (default: python on PATH)
#   BACKUP_DIR=dir  where backups go (default ~/mathkangaroo-data/backups)
#   KEEP_DAYS=n     delete this database's backups older than n days (default 14; 0 keeps all)

set -Eeuo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${PYTHON:-python}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/mathkangaroo-data/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
cd "$APP_DIR"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ "$KEEP_DAYS" =~ ^[0-9]+$ ]] || fail "KEEP_DAYS must be a whole number of days."

export DJANGO_SETTINGS_MODULE=MathKangaroo.settings
export DJANGO_DEBUG=false

config="$("$PYTHON" - <<'PY'
import shlex

from django.conf import settings

db = settings.DATABASES["default"]
values = {
    "DB_KIND": db["ENGINE"].rsplit(".", 1)[-1],
    "DB_NAME_": str(db["NAME"]),
    "DB_USER_": db.get("USER", ""),
    "DB_PASSWORD_": db.get("PASSWORD", ""),
    "DB_HOST_": db.get("HOST", "") or "localhost",
    "DB_PORT_": str(db.get("PORT", "")),
}
for name, value in values.items():
    print(f"{name}={shlex.quote(value)}")
PY
)" || fail "Django could not load the settings; run this inside the app's virtualenv or set PYTHON."
eval "$config"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
umask 077
stamp="$(date +%Y%m%d-%H%M%S)"
backup=""
# Never leave a half-written dump behind if the dump command fails.
trap 'if [[ -n "$backup" ]]; then rm -f "$backup.partial"; fi' EXIT

case "$DB_KIND" in
    postgresql)
        command -v pg_dump >/dev/null \
            || fail "pg_dump is not available. Export the database from cPanel > phpPgAdmin instead."
        backup="$BACKUP_DIR/$DB_NAME_-$stamp.dump"
        PGPASSWORD="$DB_PASSWORD_" pg_dump --format=custom --no-owner \
            --host="$DB_HOST_" --port="$DB_PORT_" --username="$DB_USER_" \
            --file="$backup.partial" "$DB_NAME_"
        ;;
    *)
        fail "There is no backup method for the '$DB_KIND' database engine."
        ;;
esac
mv "$backup.partial" "$backup"
echo "Saved $backup"

if [[ "$KEEP_DAYS" != 0 ]]; then
    find "$BACKUP_DIR" -maxdepth 1 -type f \
        \( -name "$DB_NAME_-*.dump" -o -name "$DB_NAME_-*.partial" \) \
        -mtime +"$KEEP_DAYS" -delete
fi
