# Deploying Math Kangaroo Bangladesh on cPanel

This guide puts the site at **https://kangaroomathbd.org/** on a cPanel
account that has **Setup Python App** (CloudLinux Python Selector). Passenger
runs Django; on LiteSpeed servers, LiteSpeed's Passenger-compatible runner
does. The web server (Apache or LiteSpeed) serves static files and public
uploads straight from the domain's document root. Configuration lives in one
`.env` file.

These rules are built into the settings:

- The live site always runs with `DEBUG` off. `passenger_wsgi.py` enforces
  this whatever `.env` says.
- `kangaroomathbd.org` and `www.kangaroomathbd.org` are the allowed hosts.
  The `www` address and plain HTTP both redirect to `https://kangaroomathbd.org/`.
- Production uses PostgreSQL and refuses to start with any other database.

Files in this folder:

| File | Purpose |
| --- | --- |
| `production.env.example` | Template for the production `.env` |
| `deploy.sh` | One-command deploy and update: packages, checks, backup, migrations, static files, restart |
| `backup.sh` | Database backup, used by `deploy.sh` and by the nightly cron job |
| `retire-wordpress.sh` | Moves an existing WordPress site out of the document root so Django answers `/` |
| `htaccess-document-root.txt` | Block to paste into the document root `.htaccess`: HTTPS and www redirects, no directory listings |
| `htaccess-static.txt`, `htaccess-media.txt` | Installed automatically by `deploy.sh` |

The project root also has `passenger_wsgi.py`, the startup file cPanel loads.

## Before you start

You need:

- **Setup Python App** in cPanel, offering **Python 3.10, 3.11, 3.12 or
  3.13**. Pick 3.13 if it is offered. Do **not** pick Python 3.14: the site
  runs on Django 5.1, which does not support it and breaks while rendering
  pages. `deploy.sh` stops with a clear message if the virtualenv uses the
  wrong Python.
- **Terminal** in cPanel, or SSH access.
- **PostgreSQL 13 or newer** in **cPanel › PostgreSQL Databases**. The site
  does not run on MySQL. See [Check the PostgreSQL version](#check-the-postgresql-version-first).
- `kangaroomathbd.org` and `www.kangaroomathbd.org` pointing at the account,
  with a certificate covering both.
  Check **cPanel › SSL/TLS Status**; run AutoSSL if needed.
- A mailbox for outgoing mail, `no-reply@kangaroomathbd.org`
  (**cPanel › Email Accounts**).

The site runs at the root of the domain. A sub-folder URL such as
`kangaroomathbd.org/site/` would need extra changes.

### Check the PostgreSQL version first

The site runs **Django 5.1**, which needs **PostgreSQL 13 or newer**. cPanel
uses the PostgreSQL that ships with the server's operating system:

- AlmaLinux/CloudLinux 9 ships 13 — this works.
- AlmaLinux/CloudLinux 8 ships 10 — too old.

To see your server's version, use either:

- **cPanel › phpPgAdmin**, which shows the server version on its first page;
- or, after step 1, run this in the Terminal and enter the database password:

  ```bash
  psql -h localhost -U CPANELUSER_mkweb -d CPANELUSER_mathkangaroo -c 'SHOW server_version;'
  ```

`deploy.sh` also prints the version, and stops with
"PostgreSQL 13 or later is required" if it is too old.

> **Why Django 5.1 and not 5.2?** Django 5.2 refuses to start on anything
> below PostgreSQL 14, so it cannot run on a server that offers 13.
> `requirements.txt` therefore pins `Django>=5.1,<5.2`. Django 5.1 no longer
> receives security releases, so move to Django 5.2 as soon as the host
> offers PostgreSQL 14: change the pin in `requirements.txt` back to
> `Django>=5.2,<5.3`, update the Python guard in `deploy.sh`, and redeploy.

If the version is below 13, there are two options:

- **Ask the host for PostgreSQL 13 or newer.** Some hosts can install a
  newer version.
- **Use an external managed PostgreSQL** (13 or newer). Put its host, port,
  name, user and password in `.env`, and set `DB_SSLMODE=require`. Ask the
  host to allow outgoing connections to that server's port, usually 5432;
  shared hosts often block them.

  The server's own `pg_dump` is then older than the database and cannot back
  it up. Rely on the provider's automatic backups and run deploys with
  `SKIP_BACKUP=1`. Alternatively, point `PG_DUMP=` at a `pg_dump` of the same
  or a newer version, for both `deploy.sh` and the cron job. `backup.sh`
  checks the versions and says which applies.

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

In **cPanel › PostgreSQL Databases**:

1. Create the database `mathkangaroo`.
2. Create the user `mkweb` with a long generated password of letters and
   digits only (24+ characters), so it needs no quoting in `.env`.
3. Add the user to the database and save.

cPanel adds a prefix to both names. It is usually your username
(`CPANELUSER_mathkangaroo`), but on some servers only its first 8 characters.
Copy the exact names from the **Current Databases** and **Current Users**
lists. This guide writes them as `CPANELUSER_mathkangaroo` and
`CPANELUSER_mkweb`.

### 2. Put the code on the server

Put the code **outside `public_html`**, in `/home/CPANELUSER/mathkangaroo`.
Use one of these two methods.

- **Git (recommended):** in **cPanel › Git Version Control › Create**, paste
  the repository's clone URL and set the repository path to
  `/home/CPANELUSER/mathkangaroo`.
  - A **private** GitHub repository needs a deploy key first. Git Version
    Control cannot use a key that has a passphrase. Run this in the Terminal:

    ```bash
    ssh-keygen -t ed25519 -N "" -f ~/.ssh/mathkangaroo_deploy
    printf 'Host github.com\n  IdentityFile ~/.ssh/mathkangaroo_deploy\n  IdentitiesOnly yes\n' >> ~/.ssh/config
    chmod 600 ~/.ssh/config
    cat ~/.ssh/mathkangaroo_deploy.pub
    ```

    1. On GitHub, add the printed key under the repository's
       **Settings › Deploy keys**, read-only.
    2. In Git Version Control, use the SSH clone URL
       `git@github.com:OWNER/REPOSITORY.git`, not the `https://` one.
    3. Click **Save and Continue** when asked to trust GitHub's host key.
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
in `<angle brackets>`. The domain, database type and mail server are
already filled in.

- `DJANGO_SECRET_KEY`: the generated value. Keep it secret and never reuse it.
- `DJANGO_ALLOWED_HOSTS` is already `kangaroomathbd.org,www.kangaroomathbd.org`.
  Use host names only: `https://kangaroomathbd.org/` there is refused,
  because Django would reject every request.
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`: the full prefixed names from step 1.
- `DJANGO_STATIC_ROOT`, `DJANGO_MEDIA_ROOT`: inside the domain's document root.
- `DJANGO_PRIVATE_MEDIA_ROOT`, `DJANGO_FILE_UPLOAD_TEMP_DIR`, `DJANGO_LOG_FILE`:
  under `/home/CPANELUSER/mathkangaroo-data/`.
- `EMAIL_HOST_PASSWORD`: the password of `no-reply@kangaroomathbd.org`. Check
  the server name and port in **Email Accounts › Connect Devices**. Port 465 uses `EMAIL_USE_SSL=true`. Port 587 uses
  `EMAIL_USE_SSL=false` and `EMAIL_USE_TLS=true`.
- `DJANGO_ADMINS` (optional, commented out): who gets an email when the site
  hits a server error.

`deploy.sh` refuses to run while any `<placeholder>` is left.

### 5. Retire an existing WordPress site

Skip this step if the document root is empty.

Django answers the root of the domain, so nothing else may claim it. A
WordPress install keeps `index.php` and a `# BEGIN WordPress` rewrite block in
the document root; the web server serves those first, so `https://kangaroomathbd.org/`
would keep showing WordPress however well Django is configured.

Export the WordPress database first in **cPanel › phpMyAdmin** if its content
still matters. The script does not touch the database.

```bash
source /home/CPANELUSER/virtualenv/mathkangaroo/3.12/bin/activate && cd /home/CPANELUSER/mathkangaroo
bash deploy/cpanel/retire-wordpress.sh
```

It lists what it will move and asks you to type `retire` before changing
anything. Run it with `DRY_RUN=1` first to see the list and stop.

Nothing is deleted. The script:

- moves WordPress's files and folders out of the document root into
  `~/wordpress-retired-TIMESTAMP`, which the web server cannot reach;
- leaves `static/`, `media/`, `.well-known/` and `cgi-bin/` in place, and
  reports anything else it does not recognise instead of moving it;
- removes the `# BEGIN WordPress` block, and those of the usual cache plugins,
  from the document-root `.htaccess`, keeping cPanel's Passenger block and a
  copy of the original;
- prints the one-line command that puts everything back.

The public site is WordPress until this runs and Django is deployed, so do
step 7 straight afterwards.

### 6. Add the document-root `.htaccess` block

1. In **File Manager**, open the domain's document root. Turn on
   **Settings › Show Hidden Files**.
2. Edit `.htaccess`. It already contains the
   `CLOUDLINUX PASSENGER CONFIGURATION` block; do not change that block.
3. Paste the contents of `deploy/cpanel/htaccess-document-root.txt` below it.

The block:

- sends `www.kangaroomathbd.org` and plain HTTP to `https://kangaroomathbd.org/`,
  including static and media files, which never reach Django;
- turns off directory listings;
- refuses hidden files and source or database files.

### 7. Run the deploy script

```bash
source /home/CPANELUSER/virtualenv/mathkangaroo/3.12/bin/activate && cd /home/CPANELUSER/mathkangaroo
bash deploy/cpanel/deploy.sh
```

The script stops at the first problem and says what to fix. In order, it:

1. checks that the virtualenv uses Python 3.10-3.13, then checks the `.env` file;
2. installs `requirements.txt`;
3. confirms Django loads in production mode, connects to the database and
   prints the PostgreSQL version (13+ required);
4. creates the static, media, private-media, upload-temp and log folders,
   with the private ones readable only by your account;
5. runs `manage.py check --deploy`;
6. backs up the database if migrations are pending;
7. migrates;
8. collects static files and installs the `static/` and `media/` `.htaccess` rules;
9. restarts the app, waits for it to reload, and requests the home page.

`check --deploy` always prints two warnings. Both are intentional; see
[Raise HSTS after a week](#9-raise-hsts-after-a-week).

- `security.W005`: HSTS does not cover subdomains.
- `security.W021`: the domain is not on the HSTS preload list.

### 8. Create the first staff account

```bash
python manage.py createsuperuser
```

Sign in at `https://kangaroomathbd.org/admin/`, then:

- Create staff accounts and give each one the least-privileged group that
  fits. Migrations create the groups: **Content Editor**, **Content
  Publisher**, **Competition Manager**, **Auditor** and **Account Manager**.
  The staff flag alone grants nothing.
- The migrations seed the 2027 season as open. Set the real registration
  dates and profile-edit window on the season before announcing the site.

Then check the site:

- [ ] `https://kangaroomathbd.org/` loads with styles, fonts and icons.
- [ ] `http://kangaroomathbd.org/` redirects to `https://`.
- [ ] `https://www.kangaroomathbd.org/` redirects to `https://kangaroomathbd.org/`.
- [ ] `https://kangaroomathbd.org/media/` and `https://kangaroomathbd.org/static/`
      show an error page (Not Found or Forbidden), not a file list.
- [ ] An image uploaded in the content desk (`/dashboard/content/`) appears
      on the public page.
- [ ] A test question PDF downloads from `/questions/` only after it is
      published.
- [ ] A password-reset email arrives.

### 9. Raise HSTS after a week

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

The backup job emails a one-line confirmation each night; a missing
email means it stopped. Append ` >/dev/null` to the line to get email only
for failures.

`backup.sh` keeps backups in `~/mathkangaroo-data/backups`, which is on the
same server. Download a copy now and then, or rely on the host's off-server
backups as well.

Test a restore at least once, into a scratch database, **never the live
one**:

1. Create a database such as `mkrestore` in cPanel and add `CPANELUSER_mkweb`
   to it. On PostgreSQL 15 or newer, also run
   `GRANT ALL ON SCHEMA public TO CPANELUSER_mkweb;` on that database in
   **phpPgAdmin**, signed in as your cPanel user. Otherwise the restore cannot
   create tables.
2. Restore into it, then check the tables:

   ```bash
   PGPASSWORD='<database password>' pg_restore --no-owner -h localhost -U CPANELUSER_mkweb -d CPANELUSER_mkrestore <file>.dump
   ```

3. Delete the scratch database.

Back up the uploads too. They are in `public_html/media` and
`mathkangaroo-data/private_media`.

## Logs

| What | Where |
| --- | --- |
| Django errors and warnings (look here first) | `DJANGO_LOG_FILE`, for example `~/mathkangaroo-data/logs/django.log` |
| Start-up crashes | Depends on the server, see below |
| Web server errors | **cPanel › Metrics › Errors** |

Where start-up crashes go:

- On Apache, they go to the Passenger log file set in step 3.
- On LiteSpeed, they go to `stderr.log` in the application root, but only if
  the host changed "Run on Startup" from its default.
- Otherwise they go to a server-wide log you cannot read.

When you cannot find them, reproduce the error inside the virtualenv with
`python -c "import passenger_wsgi"` and `python manage.py check --deploy`.

`django.log` is not rotated. If it grows large, empty it with
`: > ~/mathkangaroo-data/logs/django.log`; logging continues without a
restart.

Server errors are also emailed to `DJANGO_ADMINS`.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| "Web application could not be started", or a 500 on every page | Settings refused to load: a `.env` value is missing or wrong, or a package is missing | Run `python -c "import passenger_wsgi"` and `python manage.py check --deploy` in the virtualenv, and read the error. |
| `deploy.sh`: "PostgreSQL 13 or later is required" | The server's PostgreSQL is too old | See [Check the PostgreSQL version](#check-the-postgresql-version-first). |
| `deploy.sh`: "This virtualenv uses Python 3.14, but Django 5.1 needs Python 3.10-3.13" | The app was created with too new a Python | In **Setup Python App**, create the app with Python 3.13 (or 3.12/3.11/3.10), reinstall into that virtualenv, and run `deploy.sh` again. |
| `AttributeError: 'super' object has no attribute 'dicts'` on any page | Django 5.1 running on Python 3.14 | Same fix as the row above: rebuild the app on Python 3.13 or older. |
| `deploy.sh`: "Cannot use the database: ... password authentication failed" or "does not exist" | Wrong `DB_*` value | Copy the exact prefixed names from cPanel. Use a letters-and-digits password, or see the quoting note at the top of `.env`. |
| `deploy.sh`/`backup.sh`: "pg_dump N cannot back up a PostgreSQL M server" | The external database is newer than the server's `pg_dump` | See the external-PostgreSQL option in [Check the PostgreSQL version](#check-the-postgresql-version-first). |
| `migrate`: "permission denied for schema public" | PostgreSQL 15+ no longer lets every user create tables | In **phpPgAdmin**, signed in as your cPanel user, run `GRANT ALL ON SCHEMA public TO CPANELUSER_mkweb;`, or ask the host. |
| "Bad Request (400)" | The address used is not in `DJANGO_ALLOWED_HOSTS` | Use `https://kangaroomathbd.org/`. If you changed `DJANGO_ALLOWED_HOSTS`, list host names only, then restart. |
| "Too many redirects" | Cloudflare's **Flexible** SSL mode sends plain HTTP to the server | In Cloudflare, use SSL mode **Full (strict)**; that alone fixes it. Use `DJANGO_SECURE_PROXY_SSL_HEADER=true` only if you must stay on Flexible, and know that the server then trusts a header any client can send. |
| "CSRF verification failed" on forms | The origin is not trusted, or HTTPS is not detected | Keep `https://kangaroomathbd.org` in `DJANGO_CSRF_TRUSTED_ORIGINS`. Check the redirect row above. |
| The home page still shows the old WordPress site | WordPress's `index.php` and rewrite block still own the document root | Run `bash deploy/cpanel/retire-wordpress.sh`, then `deploy.sh`. |
| Every page is "Bad Request (400)", or a Django debug page saying `DisallowedHost` | The app is running without its `.env`, so `DEBUG` is on and `ALLOWED_HOSTS` is localhost-only | Check that `.env` sits in the Application root from Setup Python App, then restart. `python -c "from django.conf import settings; import django; django.setup(); print(settings.DEBUG, settings.ALLOWED_HOSTS)"` prints what the app actually loaded. |
| Unstyled pages, or 500 with "Missing staticfiles manifest entry" | Static files were not collected | Run `deploy.sh`. Check that `DJANGO_STATIC_ROOT` is inside the document root. |
| Uploaded images missing | `DJANGO_MEDIA_ROOT` is wrong, or permissions | It must match the folder under the document root. Folders need 755 and files 644. |
| `pip` fails building `psycopg` or `Pillow` | Old server OS without matching binary wheels | Pick another Python version in Setup Python App, or ask the host. |
| Large PDF uploads fail | The host's request-size limit, or a missing temp folder | Run `deploy.sh`, which creates `DJANGO_FILE_UPLOAD_TEMP_DIR`. Ask the host about the upload limit; the site accepts PDFs up to 20 MB. |
| Uploaded file names change, such as `photo.v2.jpg` becoming `photo_v2.jpg` | This is intended | Only the last extension is kept, so a web server can never treat an upload as a script. |
| Password-reset email never arrives | SMTP settings, or mail deliverability | Check the `EMAIL_*` values and port/SSL pairing. Fix SPF/DKIM in **cPanel › Email Deliverability**. |
| A `.env` change has no effect | The app was not restarted | Restart the app, or `touch tmp/restart.txt` |

## Before inviting the public

This setup covers hosting. The blueprint (`Math_Kangaroo_Bangladesh_Django_Blueprint.md`)
and `progress.md` still list these items as open before launch:

- login throttling and rate limiting;
- email verification;
- consent and child-data policies;
- an off-server backup and restore drill.
