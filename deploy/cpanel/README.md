# Deploying Math Kangaroo Bangladesh on cPanel

This guide puts the site on a cPanel account that has **Setup Python App**
(CloudLinux Python Selector). Phusion Passenger runs Django. The web server
(Apache or LiteSpeed) serves static files and public uploads straight from
the domain's document root. Configuration lives in one `.env` file.

Files in this folder:

| File | Purpose |
| --- | --- |
| `production.env.example` | Template for the production `.env` |
| `deploy.sh` | One-command deploy and update: packages, checks, backup, migrations, static files, restart |
| `backup.sh` | Database backup, used by `deploy.sh` and by the nightly cron job |
| `htaccess-document-root.txt` | Block to paste into the document root `.htaccess`: HTTPS redirect, no directory listings |
| `htaccess-static.txt`, `htaccess-media.txt` | Installed automatically by `deploy.sh` |

The project root also has `passenger_wsgi.py`, the startup file cPanel loads.

## Before you start

You need:

- **Setup Python App** in cPanel, offering Python 3.10 or newer. Pick the
  newest version offered; 3.12 or later is recommended.
- **Terminal** in cPanel, or SSH access.
- A database: **PostgreSQL Databases** (preferred) or **MySQL Databases**
  (see [Using MySQL or MariaDB](#using-mysql-or-mariadb)).
- The domain or subdomain pointing at the account, with a certificate issued.
  Check **cPanel › SSL/TLS Status**; run AutoSSL if needed.
- A mailbox for outgoing mail, such as `no-reply@your-domain`
  (**cPanel › Email Accounts**).

Deploy at the root of a domain or subdomain, for example
`https://mathkangaroo.example.org/`. A sub-folder URL such as
`example.org/kangaroo/` needs extra changes and is not covered here.

## How the pieces fit

`CPANELUSER` is the cPanel username. `public_html` stands for the domain's
document root; an addon domain or subdomain may use another folder, shown in
**cPanel › Domains**.

```text
/home/CPANELUSER/
├── mathkangaroo/                  application root (this repository), never web-visible
│   ├── passenger_wsgi.py          startup file loaded by Passenger
│   ├── .env                       production settings (chmod 600)
│   └── tmp/restart.txt            touched to restart the app
├── mathkangaroo-data/
│   ├── private_media/             question-paper PDFs, served only through Django's checks
│   ├── upload_tmp/                temporary space for large uploads
│   ├── backups/                   database backups
│   └── logs/django.log            application log
├── virtualenv/mathkangaroo/3.12/  created by cPanel
└── public_html/                   domain document root
    ├── .htaccess                  cPanel's Passenger block plus our block
    ├── static/                    collected CSS, JS, fonts, images
    └── media/                     public uploads: hero, announcement and About images
```

Question-paper PDFs never go under `public_html`, because files there can be
downloaded by anyone who guesses the URL. Django serves them only after
checking that the paper is published. The settings refuse to start if
`DJANGO_PRIVATE_MEDIA_ROOT` points inside `public_html` or the media folder.

## First deployment

### 1. Create the database

**PostgreSQL:** in **cPanel › PostgreSQL Databases**:

1. Create the database `mathkangaroo`. cPanel names it `CPANELUSER_mathkangaroo`.
2. Create the user `mkweb` with a long generated password. cPanel names it `CPANELUSER_mkweb`.
3. Add the user to the database and save.

To use MySQL instead, see [Using MySQL or MariaDB](#using-mysql-or-mariadb).

### 2. Put the code on the server

Put the code **outside `public_html`**, in `/home/CPANELUSER/mathkangaroo`.
Use one of these two methods.

- **Git (recommended):** in **cPanel › Git Version Control › Create**, paste
  the repository's clone URL and set the repository path to
  `/home/CPANELUSER/mathkangaroo`.
  - For a private GitHub repository, first create a key in **cPanel › SSH
    Access**, then add its public key to the repository as a read-only
    deploy key.
- **Upload:** zip the project on your computer and upload it with **File
  Manager**, then extract it into `/home/CPANELUSER/mathkangaroo`. Leave out
  `.venv/`, `.env`, `db.sqlite3`, `media/` and `staticfiles/`.

### 3. Create the Python application

In **cPanel › Setup Python App › Create Application**:

| Field | Value |
| --- | --- |
| Python version | Newest offered, at least 3.10 |
| Application root | `mathkangaroo` |
| Application URL | The domain, with the path left empty |
| Application startup file | `passenger_wsgi.py` |
| Application Entry point | `application` |
| Passenger log file, if shown | `/home/CPANELUSER/mathkangaroo-data/logs/passenger.log` |

Leave the environment-variables section empty, because the `.env` file holds
the settings. A value set there overrides the same value in `.env`.

Click **Create**. Some cPanel versions replace `passenger_wsgi.py` with a
"It works!" sample. If the file no longer mentions `MathKangaroo.settings`,
restore it with `git checkout passenger_wsgi.py`, or upload it again.

At the top of the app page, cPanel shows a command that starts with
`source /home/CPANELUSER/virtualenv/...`. Copy it. Every terminal step below
starts with that command.

### 4. Write the `.env` file

Open **cPanel › Terminal** and run:

```bash
source /home/CPANELUSER/virtualenv/mathkangaroo/3.12/bin/activate && cd /home/CPANELUSER/mathkangaroo
cp deploy/cpanel/production.env.example .env
chmod 600 .env
python -c "import secrets; print(secrets.token_urlsafe(50))"   # copy the output for DJANGO_SECRET_KEY
```

Edit `.env` with `nano .env` or the File Manager editor. Replace every value
in `<angle brackets>` and every `example.org`:

- `DJANGO_SECRET_KEY`: the generated value. Keep it secret and never reuse it.
- `DJANGO_ALLOWED_HOSTS`: the domain(s), comma-separated, without `https://`.
- `DJANGO_CSRF_TRUSTED_ORIGINS`: the same domain(s), with `https://`.
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`: the full prefixed names from step 1.
- `DJANGO_STATIC_ROOT`, `DJANGO_MEDIA_ROOT`: inside the domain's document root.
- `DJANGO_PRIVATE_MEDIA_ROOT`, `DJANGO_FILE_UPLOAD_TEMP_DIR`, `DJANGO_LOG_FILE`:
  under `/home/CPANELUSER/mathkangaroo-data/`.
- `EMAIL_*`: copy them from **Email Accounts › Connect Devices** for the
  mailbox. Port 465 uses `EMAIL_USE_SSL=true`. Port 587 uses
  `EMAIL_USE_SSL=false` and `EMAIL_USE_TLS=true`.
- `DJANGO_ADMINS`: who gets an email when the site hits a server error.

`deploy.sh` refuses to run while any `<placeholder>` is left.

### 5. Add the document-root `.htaccess` block

1. In **File Manager**, open the domain's document root. Turn on
   **Settings › Show Hidden Files**.
2. Edit `.htaccess`. It already contains the
   `CLOUDLINUX PASSENGER CONFIGURATION` block; do not change that block.
3. Paste the contents of `deploy/cpanel/htaccess-document-root.txt` below it.

The block:

- redirects HTTP to HTTPS, including static and media files, which never
  reach Django;
- turns off directory listings;
- refuses hidden files and source or database files.

### 6. Run the deploy script

```bash
source /home/CPANELUSER/virtualenv/mathkangaroo/3.12/bin/activate && cd /home/CPANELUSER/mathkangaroo
bash deploy/cpanel/deploy.sh
```

The script stops at the first problem and says what to fix. In order, it:

1. checks the `.env` file;
2. installs `requirements.txt`;
3. confirms Django loads in production mode and can reach the database
   (`manage.py check --deploy --database default`);
4. backs up the database if migrations are pending;
5. migrates;
6. creates the upload folders with tight permissions;
7. collects static files and installs the `static/` and `media/` `.htaccess` rules;
8. restarts the app and requests the home page.

`check --deploy` always prints two warnings. Both are intentional; see
[Raise HSTS after a week](#8-raise-hsts-after-a-week).

- `security.W005`: HSTS does not cover subdomains.
- `security.W021`: the domain is not on the HSTS preload list.

### 7. Create the first staff account

```bash
python manage.py createsuperuser
```

Sign in at `https://your-domain/admin/`, then:

- Create staff accounts and give each one the least-privileged group that
  fits. Migrations create the groups: **Content Editor**, **Content
  Publisher**, **Competition Manager**, **Auditor** and **Account Manager**.
  The staff flag alone grants nothing.
- The migrations seed the 2027 season as open. Set the real registration
  dates and profile-edit window on the season before announcing the site.

Then check the site:

- [ ] `https://your-domain/` loads with styles, fonts and icons.
- [ ] `http://your-domain/` redirects to `https://`.
- [ ] `https://your-domain/media/` and `https://your-domain/static/` show
      "Forbidden", not a file list.
- [ ] An image uploaded in the content desk (`/dashboard/content/`) appears
      on the public page.
- [ ] A test question PDF downloads from `/questions/` only after it is
      published.
- [ ] A password-reset email arrives.

### 8. Raise HSTS after a week

Once the site has worked over HTTPS for about a week, set
`DJANGO_SECURE_HSTS_SECONDS=31536000` in `.env`, then restart the app.
Browsers will then refuse plain HTTP for this host for a year.

Turn on `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` and
`DJANGO_SECURE_HSTS_PRELOAD` only if every subdomain serves HTTPS. That
includes webmail, cpanel and any other site on the domain. Preloading is very
hard to undo.

## Updating the site

```bash
source /home/CPANELUSER/virtualenv/mathkangaroo/3.12/bin/activate && cd /home/CPANELUSER/mathkangaroo
git pull                      # or: cPanel › Git Version Control › Manage › Pull or Deploy › Update from Remote
bash deploy/cpanel/deploy.sh
```

The script backs up the database before it applies new migrations. To change
only `.env`, restart the app instead: click **Restart** in Setup Python App,
or run `touch tmp/restart.txt`.

The `0004_backfill_participant_usernames` migration rewrites the usernames
of older accounts. On a database that already holds real accounts, keep the
backup the script makes, and review the effect on login instructions before
you continue.

## Scheduled jobs

In **cPanel › Cron Jobs**, add these jobs. Replace `CPANELUSER` and the
Python version, and keep each command on one line.

Every night at 02:30, back up the database and keep 14 days of backups:

```text
PYTHON=/home/CPANELUSER/virtualenv/mathkangaroo/3.12/bin/python /bin/bash /home/CPANELUSER/mathkangaroo/deploy/cpanel/backup.sh
```

Every day at 03:15, remove expired login sessions:

```text
cd /home/CPANELUSER/mathkangaroo && /home/CPANELUSER/virtualenv/mathkangaroo/3.12/bin/python manage.py clearsessions
```

`backup.sh` keeps backups in `~/mathkangaroo-data/backups`, which is on the
same server. Download a copy now and then, or rely on the host's off-server
backups as well. Test a restore at least once:

- PostgreSQL: `pg_restore --no-owner -d <database> <file>.dump`
- MySQL: `gunzip -c <file>.sql.gz | mysql <database>`

Back up the uploads too. They are in `public_html/media` and
`mathkangaroo-data/private_media`.

## Using MySQL or MariaDB

Use MySQL or MariaDB only if the host offers no PostgreSQL. Django 5.2 needs
MariaDB 10.5+ or MySQL 8.0.11+.

1. Create the database and user in **cPanel › MySQL Databases**, and grant the
   user **ALL PRIVILEGES** on it.
2. In `.env`, set `DB_ENGINE=mysql` and `DB_PORT=3306`.

The pure-Python PyMySQL driver in `requirements.txt` is used, so nothing has
to be compiled.

One limit: MySQL and MariaDB cannot enforce the database rule that only one
competition season is marked current. `check --deploy` reports this as
`models.W036`. Make sure only one season is marked current in the admin.

## Logs

| What | Where |
| --- | --- |
| Django errors and warnings | `DJANGO_LOG_FILE`, for example `~/mathkangaroo-data/logs/django.log` |
| Start-up crashes and anything printed to stderr | The Passenger log file set in step 3, or `stderr.log` in the application root |
| Web server errors | **cPanel › Metrics › Errors** |

Server errors are also emailed to `DJANGO_ADMINS`.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| "Web application could not be started", or a 500 on every page | Settings refused to load: a `.env` value is missing or wrong, or a package is missing | Run `python manage.py check --deploy` in the virtualenv and read the error. Check the Passenger log. |
| "Bad Request (400)" | The domain is not in `DJANGO_ALLOWED_HOSTS` | Add it and restart |
| "Too many redirects" | HTTPS is handled by a proxy such as Cloudflare, and Django sees plain HTTP | In Cloudflare, use SSL mode **Full (strict)** and set `DJANGO_SECURE_PROXY_SSL_HEADER=true`. As a last resort, set `DJANGO_SECURE_SSL_REDIRECT=false`; the `.htaccess` block still redirects. |
| "CSRF verification failed" on forms | The origin is not trusted, or HTTPS is not detected | Put `https://your-domain` in `DJANGO_CSRF_TRUSTED_ORIGINS`. Check the redirect row above. |
| Unstyled pages, or 500 with "Missing staticfiles manifest entry" | Static files were not collected | Run `deploy.sh`. Check that `DJANGO_STATIC_ROOT` is inside the document root. |
| Uploaded images missing | `DJANGO_MEDIA_ROOT` is wrong, or permissions | It must match the folder under the document root. Folders need 755 and files 644. |
| `pip` fails building `psycopg` or `Pillow` | Old server OS without matching binary wheels | Pick another Python version in Setup Python App, or ask the host. Use MySQL only if PostgreSQL is the problem. |
| Large PDF uploads fail | The host's request-size limit, or a missing temp folder | Run `deploy.sh`, which creates `DJANGO_FILE_UPLOAD_TEMP_DIR`. Ask the host about the upload limit; the site accepts PDFs up to 20 MB. |
| Password-reset email never arrives | SMTP settings, or mail deliverability | Check the `EMAIL_*` values and port/SSL pairing. Fix SPF/DKIM in **cPanel › Email Deliverability**. |
| A `.env` change has no effect | The app was not restarted | Restart the app, or `touch tmp/restart.txt` |

## Before inviting the public

This setup covers hosting. The blueprint (`Math_Kangaroo_Bangladesh_Django_Blueprint.md`)
and `progress.md` still list these items as open before launch:

- login throttling and rate limiting;
- email verification;
- consent and child-data policies;
- an off-server backup and restore drill.
