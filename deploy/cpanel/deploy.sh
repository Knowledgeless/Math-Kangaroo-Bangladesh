#!/usr/bin/env bash
# Deploy or update Math Kangaroo Bangladesh on cPanel.
#
# Run from the cPanel Terminal (or SSH) inside the application's virtualenv.
# cPanel > Setup Python App shows the exact command at the top of the app page:
#
#   source /home/CPANELUSER/virtualenv/mathkangaroo/3.12/bin/activate && cd /home/CPANELUSER/mathkangaroo
#   bash deploy/cpanel/deploy.sh
#
# What it does: installs requirements, validates production settings, backs up
# the database when migrations are pending, migrates, collects static files,
# installs the static/media .htaccess files, and restarts the app.
#
# Options (environment variables):
#   SKIP_PIP=1      do not install requirements
#   SKIP_BACKUP=1   do not back up the database before migrating
#   BACKUP_DIR=dir  where database backups go (default ~/mathkangaroo-data/backups)
#   KEEP_DAYS=n     prune this database's backups older than n days (default 14)

set -Eeuo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEMPLATE_DIR="$APP_DIR/deploy/cpanel"
HTACCESS_MARKER="# Managed by deploy/cpanel/deploy.sh"
cd "$APP_DIR"

step() { printf '\n==> %s\n' "$*"; }
warn() { printf 'WARNING: %s\n' "$*" >&2; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }
trap 'fail "deploy stopped at line $LINENO; nothing after that step ran."' ERR

[[ -n "${VIRTUAL_ENV:-}" ]] || fail "Enter the app's virtualenv first (cPanel > Setup Python App shows the 'source .../bin/activate' command)."
[[ -f manage.py && -f passenger_wsgi.py ]] || fail "Run this from a checkout of the project ($APP_DIR has no manage.py/passenger_wsgi.py)."

# Same production defaults as passenger_wsgi.py.
export DJANGO_SETTINGS_MODULE=MathKangaroo.settings
export DJANGO_DEBUG_DEFAULT=false

step "Checking the .env file"
ENV_FILE="${DJANGO_ENV_FILE:-$APP_DIR/.env}"
if [[ -f "$ENV_FILE" ]]; then
    # Template placeholders look like <CPANELUSER>; e-mail addresses (<a@b>) are fine.
    placeholders="$(grep -Eo '^[A-Za-z_][A-Za-z0-9_]*=.*<[^>@]*>' "$ENV_FILE" | cut -d= -f1 | paste -sd, - || true)"
    [[ -z "$placeholders" ]] || fail "$ENV_FILE still has <placeholder> values for: $placeholders"
    if grep -Eq '^[^#]*example\.org' "$ENV_FILE"; then
        warn "$ENV_FILE still mentions example.org; replace it with the real domain."
    fi
    if [[ "$(stat -c '%a' "$ENV_FILE")" != 600 ]]; then
        chmod 600 "$ENV_FILE"
        echo "Restricted $ENV_FILE to its owner (chmod 600)."
    fi
    echo "Using $ENV_FILE"
else
    warn "No $ENV_FILE; using environment variables only."
fi

if [[ "${SKIP_PIP:-0}" != 1 ]]; then
    step "Installing Python packages"
    python -m pip install --disable-pip-version-check -r requirements.txt
fi

step "Validating production settings"
config="$(python - <<'PY'
import shlex

import django
from django.conf import settings

django.setup()
db = settings.DATABASES["default"]
values = {
    "CFG_DEBUG": "1" if settings.DEBUG else "0",
    "CFG_ENGINE": db["ENGINE"].rsplit(".", 1)[-1],
    "CFG_DB_NAME": str(db["NAME"]),
    "CFG_DB_HOST": db.get("HOST", ""),
    "CFG_DB_PORT": str(db.get("PORT", "")),
    "CFG_STATIC_ROOT": str(settings.STATIC_ROOT),
    "CFG_MEDIA_ROOT": str(settings.MEDIA_ROOT),
    "CFG_PRIVATE_MEDIA_ROOT": str(settings.PRIVATE_MEDIA_ROOT),
    "CFG_UPLOAD_TMP": settings.FILE_UPLOAD_TEMP_DIR or "",
    "CFG_EMAIL_BACKEND": settings.EMAIL_BACKEND,
    "CFG_EMAIL_HOST": settings.EMAIL_HOST,
    "CFG_HOST": next(
        (host for host in settings.ALLOWED_HOSTS if not host.startswith((".", "*"))), ""
    ),
}
for name, value in values.items():
    print(f"{name}={shlex.quote(value)}")
PY
)" || fail "Django could not load the production settings (see the error above)."
eval "$config"

[[ "$CFG_DEBUG" == 0 ]] || fail "DEBUG is on. Set DJANGO_DEBUG=false in $ENV_FILE."
echo "Database:       $CFG_ENGINE $CFG_DB_NAME on ${CFG_DB_HOST:-localhost}:$CFG_DB_PORT"
echo "Static files:   $CFG_STATIC_ROOT"
echo "Public media:   $CFG_MEDIA_ROOT"
echo "Private media:  $CFG_PRIVATE_MEDIA_ROOT"
if [[ "$CFG_EMAIL_BACKEND" == *smtp* && -z "$CFG_EMAIL_HOST" ]]; then
    warn "EMAIL_HOST is empty, so password-reset e-mails will fail."
fi

python manage.py check --deploy --database default

step "Checking for unapplied migrations"
if python manage.py migrate --check >/dev/null 2>&1; then
    echo "Database schema is up to date."
    pending=0
else
    python manage.py showmigrations --plan | grep -F '[ ]' || true
    pending=1
fi

if [[ "$pending" == 1 && "${SKIP_BACKUP:-0}" != 1 ]]; then
    step "Backing up the database before migrating"
    PYTHON="$(command -v python)" bash "$TEMPLATE_DIR/backup.sh" \
        || fail "The backup failed. Back up from cPanel (phpPgAdmin/phpMyAdmin), then rerun with SKIP_BACKUP=1."
fi

step "Applying migrations"
python manage.py migrate --noinput

step "Preparing file directories"
mkdir -p "$CFG_STATIC_ROOT" "$CFG_MEDIA_ROOT" "$CFG_PRIVATE_MEDIA_ROOT"
chmod 755 "$CFG_STATIC_ROOT" "$CFG_MEDIA_ROOT"
chmod 700 "$CFG_PRIVATE_MEDIA_ROOT"
if [[ -n "$CFG_UPLOAD_TMP" ]]; then
    mkdir -p "$CFG_UPLOAD_TMP"
    chmod 700 "$CFG_UPLOAD_TMP"
fi
if [[ -d "$CFG_MEDIA_ROOT/question-papers" ]] && compgen -G "$CFG_MEDIA_ROOT/question-papers/*" >/dev/null; then
    warn "$CFG_MEDIA_ROOT/question-papers has files from an older install. Move them to $CFG_PRIVATE_MEDIA_ROOT/question-papers/ (the download view reads them from there)."
fi

step "Collecting static files"
python manage.py collectstatic --noinput

install_htaccess() {
    local template="$1" target="$2/.htaccess"
    if [[ -f "$target" ]] && ! grep -qF "$HTACCESS_MARKER" "$target"; then
        warn "$target was not written by this script, so it was left unchanged. Compare it with $template."
        return 0
    fi
    cp "$template" "$target"
    chmod 644 "$target"
    echo "Installed $target"
}

step "Installing .htaccess rules for static and media files"
install_htaccess "$TEMPLATE_DIR/htaccess-static.txt" "$CFG_STATIC_ROOT"
install_htaccess "$TEMPLATE_DIR/htaccess-media.txt" "$CFG_MEDIA_ROOT"

document_root_htaccess="$(dirname "$CFG_STATIC_ROOT")/.htaccess"
if [[ ! -f "$document_root_htaccess" ]] || ! grep -q "PassengerAppRoot" "$document_root_htaccess"; then
    warn "$document_root_htaccess has no Passenger block. Create the app in cPanel > Setup Python App, or check that DJANGO_STATIC_ROOT is inside the domain's document root."
elif ! grep -qF "BEGIN Math Kangaroo Bangladesh" "$document_root_htaccess"; then
    warn "Add the block from deploy/cpanel/htaccess-document-root.txt to $document_root_htaccess (HTTPS redirect, no directory listings)."
fi

step "Restarting the application"
mkdir -p tmp
touch tmp/restart.txt
echo "Passenger reloads the app on the next request."

if [[ -n "$CFG_HOST" ]] && command -v curl >/dev/null; then
    step "Checking https://$CFG_HOST/"
    status="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 60 "https://$CFG_HOST/" || true)"
    if [[ "$status" == 200 ]]; then
        echo "The home page answered 200 OK."
    else
        warn "The home page answered '${status:-no response}'. Check the logs listed in deploy/cpanel/README.md."
    fi
fi

trap - ERR
printf '\nDeploy finished.\n'
