#!/usr/bin/env bash
# Retire the WordPress site in the document root so Django answers
# https://kangaroomathbd.org/ at the root of the domain.
#
# Run from the cPanel Terminal (or SSH) inside the application's virtualenv,
# BEFORE deploy.sh:
#
#   source /home/CPANELUSER/virtualenv/APPNAME/3.13/bin/activate && cd /home/CPANELUSER/APPNAME
#   bash deploy/cpanel/retire-wordpress.sh
#   bash deploy/cpanel/deploy.sh
#
# Nothing is deleted. Every WordPress file and folder is MOVED out of the
# document root into a dated archive folder that the web server cannot reach,
# and the WordPress rewrite block is removed from .htaccess. The original
# .htaccess is kept in the archive. The script prints the command that puts
# everything back.
#
# The WordPress MySQL database is NOT touched. Export it first in
# cPanel > phpMyAdmin if the content still matters.
#
# Options (environment variables):
#   DOCROOT=dir       document root (default: from DJANGO_STATIC_ROOT, else ~/public_html)
#   ARCHIVE_DIR=dir   where WordPress is moved (default ~/wordpress-retired-TIMESTAMP)
#   DRY_RUN=1         list what would move, change nothing
#   CONFIRM=yes       skip the typed confirmation (for an unattended run)

set -Eeuo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$APP_DIR"

step() { printf '\n==> %s\n' "$*"; }
warn() { printf 'WARNING: %s\n' "$*" >&2; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }
trap 'fail "stopped at line $LINENO; nothing after that step ran."' ERR

DRY_RUN="${DRY_RUN:-0}"
[[ "$DRY_RUN" == 1 ]] && echo "DRY RUN: nothing will be moved or edited."

# --- Find the document root -------------------------------------------------

step "Locating the document root"
if [[ -z "${DOCROOT:-}" ]]; then
    # Ask Django, so this agrees with DJANGO_STATIC_ROOT in .env.
    DOCROOT="$(
        DJANGO_SETTINGS_MODULE=MathKangaroo.settings DJANGO_DEBUG=false \
        python -c 'import os
from pathlib import Path
try:
    from django.conf import settings
    import django; django.setup()
    print(Path(settings.STATIC_ROOT).resolve().parent)
except Exception:
    print(Path.home() / "public_html")' 2>/dev/null || true
    )"
fi
[[ -n "$DOCROOT" ]] || DOCROOT="$HOME/public_html"
DOCROOT="$(realpath -m -- "$DOCROOT")"

[[ -d "$DOCROOT" ]] || fail "$DOCROOT is not a folder. Set DOCROOT=... to the document root shown in cPanel > Domains."
[[ "$DOCROOT" != "$HOME" && "$DOCROOT" != "/" ]] || fail "$DOCROOT is not a document root. Set DOCROOT=... explicitly."
case "$APP_DIR/" in
    "$DOCROOT"/*) fail "The application lives inside $DOCROOT. Move the code outside the document root first (see deploy/cpanel/README.md)." ;;
esac
echo "Document root: $DOCROOT"

[[ -f "$DOCROOT/.htaccess" ]] && grep -q "PassengerAppRoot" "$DOCROOT/.htaccess" \
    || warn "$DOCROOT/.htaccess has no Passenger block. Create the app in cPanel > Setup Python App first, or Django cannot answer once WordPress is gone."

# --- Is this actually WordPress? -------------------------------------------

step "Looking for WordPress"
is_wordpress=0
[[ -f "$DOCROOT/wp-config.php" || -d "$DOCROOT/wp-includes" || -d "$DOCROOT/wp-admin" ]] && is_wordpress=1
[[ -f "$DOCROOT/index.php" ]] && grep -qi "wp-blog-header" "$DOCROOT/index.php" 2>/dev/null && is_wordpress=1
[[ "$is_wordpress" == 1 ]] || fail "No WordPress found in $DOCROOT. Nothing to retire; check DOCROOT."

# Known WordPress entries. Anything else is reported, never moved.
WP_ENTRIES=(
    index.php xmlrpc.php wp-config.php wp-config-sample.php wp-activate.php
    wp-blog-header.php wp-comments-post.php wp-cron.php wp-links-opml.php
    wp-load.php wp-login.php wp-mail.php wp-settings.php wp-signup.php
    wp-trackback.php wp-admin wp-content wp-includes
    license.txt readme.html wp-config.php.bak
)
# Keep: Django's own folders, AutoSSL validation, cPanel's cgi-bin.
KEEP_ENTRIES=(static media .htaccess .well-known cgi-bin)

to_move=()
for name in "${WP_ENTRIES[@]}"; do
    [[ -e "$DOCROOT/$name" ]] && to_move+=("$name")
done
# Catch plugin leftovers such as wp-cache-config.php without a wildcard move.
while IFS= read -r -d '' path; do
    name="$(basename -- "$path")"
    [[ " ${to_move[*]} " == *" $name "* ]] || to_move+=("$name")
done < <(find "$DOCROOT" -maxdepth 1 -name 'wp-*' -print0 2>/dev/null)

echo "Will move ${#to_move[@]} entries:"
printf '  %s\n' "${to_move[@]}"

leftovers=()
while IFS= read -r -d '' path; do
    name="$(basename -- "$path")"
    [[ " ${to_move[*]} " == *" $name "* ]] && continue
    [[ " ${KEEP_ENTRIES[*]} " == *" $name "* ]] && continue
    leftovers+=("$name")
done < <(find "$DOCROOT" -mindepth 1 -maxdepth 1 -print0)

if ((${#leftovers[@]})); then
    warn "Left in place because they are not WordPress and not Django's. Review them yourself:"
    printf '  %s\n' "${leftovers[@]}" >&2
fi

# --- Confirm ----------------------------------------------------------------

ARCHIVE_DIR="${ARCHIVE_DIR:-$HOME/wordpress-retired-$(date +%Y%m%d-%H%M%S)}"
ARCHIVE_DIR="$(realpath -m -- "$ARCHIVE_DIR")"
case "$ARCHIVE_DIR/" in
    "$DOCROOT"/*) fail "ARCHIVE_DIR must be outside the document root, or the files stay downloadable." ;;
esac

cat <<EOF

This replaces the public WordPress site at the domain root with Django.
  From:    $DOCROOT
  Archive: $ARCHIVE_DIR
The WordPress MySQL database is not touched. Export it in cPanel > phpMyAdmin
first if its content still matters.
EOF

if [[ "$DRY_RUN" == 1 ]]; then
    step "Dry run finished. Nothing changed."
    exit 0
fi

if [[ "${CONFIRM:-}" != yes ]]; then
    read -r -p "Type 'retire' to continue: " answer
    [[ "$answer" == retire ]] || fail "Cancelled; nothing changed."
fi

# --- Move WordPress out -----------------------------------------------------

step "Moving WordPress to $ARCHIVE_DIR"
mkdir -p "$ARCHIVE_DIR"
chmod 700 "$ARCHIVE_DIR"
for name in "${to_move[@]}"; do
    mv -- "$DOCROOT/$name" "$ARCHIVE_DIR/"
    echo "  moved $name"
done

# --- Clean the document-root .htaccess --------------------------------------

step "Removing WordPress rules from .htaccess"
htaccess="$DOCROOT/.htaccess"
if [[ -f "$htaccess" ]]; then
    cp -p "$htaccess" "$ARCHIVE_DIR/.htaccess.original"
    # Drops "# BEGIN <name>" ... "# END <name>" blocks written by WordPress and
    # its cache plugins. cPanel's Passenger block uses a different marker
    # ("DO NOT REMOVE. CLOUDLINUX PASSENGER CONFIGURATION"), so it is kept.
    awk '
        function trim(s) { sub(/\r$/, "", s); sub(/[ \t]+$/, "", s); return s }
        /^# BEGIN / {
            name = trim(substr($0, 9))
            if (name ~ /^(WordPress|LSCACHE|NON_LSCACHE|WP Rocket|W3TC|WpFastestCache|Really Simple SSL|Wordfence|All In One WP Security|iThemes Security|EWWW)/) {
                skip = 1; dropping = name; next
            }
        }
        skip && /^# END / {
            if (trim(substr($0, 7)) == dropping) { skip = 0; next }
        }
        !skip
    ' "$htaccess" > "$htaccess.new"

    if cmp -s "$htaccess" "$htaccess.new"; then
        rm -f "$htaccess.new"
        echo "No WordPress blocks found in .htaccess; left unchanged."
    else
        mv -- "$htaccess.new" "$htaccess"
        chmod 644 "$htaccess"
        echo "Removed the WordPress blocks. Original: $ARCHIVE_DIR/.htaccess.original"
    fi

    grep -q "PassengerAppRoot" "$htaccess" \
        || warn "The Passenger block is gone from $htaccess. Restore it from $ARCHIVE_DIR/.htaccess.original, or recreate the app in cPanel > Setup Python App."
    grep -qF "BEGIN Math Kangaroo Bangladesh" "$htaccess" \
        || warn "Now paste deploy/cpanel/htaccess-document-root.txt into $htaccess, below the Passenger block."
else
    warn "$htaccess does not exist. Create the app in cPanel > Setup Python App, then paste deploy/cpanel/htaccess-document-root.txt into it."
fi

# --- Done -------------------------------------------------------------------

cat <<EOF

==> WordPress retired.

Next:
  1. Paste deploy/cpanel/htaccess-document-root.txt into $htaccess
     (below the Passenger block) if it is not there yet.
  2. bash deploy/cpanel/deploy.sh
     It recreates static/ and media/ in the document root and restarts Django.

To undo, move everything back and restore the old rules:
  mv "$ARCHIVE_DIR"/* "$DOCROOT"/ && cp -p "$ARCHIVE_DIR/.htaccess.original" "$htaccess"

If https://kangaroomathbd.org/ answers 403 or shows a file list once Django is
live, add this line to $htaccess, above the Passenger block:
  DirectoryIndex disabled
EOF
