# Math Kangaroo Bangladesh

A server-rendered Django competition website foundation with a custom public frontend, participant-ID student accounts, annual Olympiad registrations, publication workflows, and season-aware syllabus data.

## Run locally

Use Python 3.10 or newer (3.12+ recommended) with Django 5.2.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The local development default is SQLite with `DEBUG` on; no `.env` file is needed. Settings are read from environment variables, and a `.env` file in the project root (see `.env.example`) fills in anything not already set.

## Deploy

Production runs with `DJANGO_DEBUG=false` and refuses to start without `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` and a PostgreSQL database (`DB_ENGINE=postgresql`; MySQL/MariaDB via `DB_ENGINE=mysql` only where the host has no PostgreSQL).

For cPanel hosting follow [`deploy/cpanel/README.md`](deploy/cpanel/README.md): it covers the Passenger entry point (`passenger_wsgi.py`), the production `.env` template, `.htaccess` rules, the `deploy.sh` update script, backups and cron jobs.

Static files are collected into `DJANGO_STATIC_ROOT` and served by the web server, with WhiteNoise as a fallback. Public uploads go to `DJANGO_MEDIA_ROOT`. Question-paper PDFs go to `DJANGO_PRIVATE_MEDIA_ROOT`, which must stay outside every web-served folder; they are only downloadable through the publication-checked view. Django's `/media/` fallback view never serves them.

Password reset messages print to the development console. In production set the SMTP variables (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_SSL`/`EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`).

Default staff Groups are synchronized after migrations: **Content Editor**, **Content Publisher**, **Competition Manager** and **Auditor**. Assign users to the least-privileged matching Group through `/admin/`; combine editor and publisher groups only for staff who have explicit publishing authority. The custom content desk lives at `/dashboard/content/`.

## Current product slice

- Public home, announcements (search, category/year filters, pagination), FAQ, syllabus and approved practice resources.
- Student self-registration for the current open season, participant-number username login, password reset, student profile, and yearly registration history.
- Returning students register for each season separately with their current school and grade; their participant login username remains unchanged.
- Profile changes are permitted only during the profile-edit window configured by staff/admin on the season.
- Season, level, grade division, registration-sequence, annual-registration and versioned syllabus data models.
- Staff-only content desk for hero slides, announcement drafts/publishing/archiving, and FAQ drafts/publishing.
- Managed About page with a Word-like rich-text editor for headings, emphasis, font sizes, lists, and links.
- Publication dates gate scheduled public content; drafts and archived material do not appear in public querysets.
- Content publication and archive actions are recorded in an append-only audit log.
- Responsive custom CSS following the supplied UI showcase layout while preserving the existing palette; accessible dashboard reminder and keyboard-operable syllabus-level tabs.
- Light mode is the default for visitors; an explicit dark-mode choice is saved in the browser and restored on return. Responsive navigation, FAQ filters, focus styling and reduced-motion support are included.

The `/admin/` interface is retained as a technical break-glass tool; it is not the public content workflow.

## Checks

```bash
python manage.py check
python manage.py test apps.core.tests apps.accounts.tests apps.cms.tests apps.competitions.tests
```
