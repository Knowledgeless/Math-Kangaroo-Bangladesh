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
#   PG_DUMP=path    pg_dump to use; its major version must be at least the
#                   server's (default: pg_dump on PATH)
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
import sys

import django
from django.conf import settings

django.setup()
from django.db import connection

try:
    server_major = str(connection.get_database_version()[0])
except Exception as error:
    sys.exit(f"Cannot use the database: {error}")

db = settings.DATABASES["default"]
values = {
    "DB_KIND": db["ENGINE"].rsplit(".", 1)[-1],
    "DB_NAME_": str(db["NAME"]),
    "DB_USER_": db.get("USER", ""),
    "DB_PASSWORD_": db.get("PASSWORD", ""),
    "DB_HOST_": db.get("HOST", "") or "localhost",
    "DB_PORT_": str(db.get("PORT", "")),
    "DB_SERVER_MAJOR": server_major,
}
for name, value in values.items():
    print(f"{name}={shlex.quote(value)}")
PY
)" || fail "Django could not load the settings or reach the database (see above). Run this inside the app's virtualenv or set PYTHON."
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
        PG_DUMP="${PG_DUMP:-pg_dump}"
        command -v "$PG_DUMP" >/dev/null \
            || fail "pg_dump is not available. Export the database from cPanel > phpPgAdmin instead."
        # pg_dump refuses servers newer than itself (for example cPanel's
        # pg_dump 13 against an external PostgreSQL 16).
        client_major="$("$PG_DUMP" --version | grep -oE '[0-9]+' | head -n 1)"
        if (( client_major < DB_SERVER_MAJOR )); then
            fail "pg_dump $client_major cannot back up a PostgreSQL $DB_SERVER_MAJOR server. Use your database provider's backups, or set PG_DUMP to a pg_dump $DB_SERVER_MAJOR or newer."
        fi
        backup="$BACKUP_DIR/$DB_NAME_-$stamp.dump"
        PGPASSWORD="$DB_PASSWORD_" "$PG_DUMP" --format=custom --no-owner \
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
