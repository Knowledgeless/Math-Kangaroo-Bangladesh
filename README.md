# Math Kangaroo Bangladesh

A server-rendered Django competition website foundation with a custom public frontend, participant-ID student accounts, annual Olympiad registrations, publication workflows, and season-aware syllabus data.

## Run locally

Use Python 3.13 or newer with Django 5.2.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The local development default is SQLite. Production requires PostgreSQL and explicit environment configuration:

```text
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<secret from the deployment secret manager>
DJANGO_ALLOWED_HOSTS=your-domain.example
DB_ENGINE=postgresql
DB_NAME=...
DB_USER=...
DB_PASSWORD=...
DB_HOST=...
DB_PORT=5432
```

Password reset messages print to the development console. Set the SMTP environment variables and `DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` to send real email.

Default staff Groups are synchronized after migrations: **Content Editor**, **Content Publisher**, **Competition Manager** and **Auditor**. Assign users to the least-privileged matching Group through `/admin/`; combine editor and publisher groups only for staff who have explicit publishing authority. The custom content desk lives at `/dashboard/content/`.

## Current product slice

- Public home, announcements (search, category/year filters, pagination), FAQ, syllabus and approved practice resources.
- Student self-registration for the current open season, participant-number username login, password reset, student profile, and yearly registration history.
- Returning students register for each season separately with their current school and grade; their participant login username remains unchanged.
- Profile changes are permitted only during the profile-edit window configured by staff/admin on the season.
- Season, level, grade division, registration-sequence, annual-registration and versioned syllabus data models.
- Staff-only content desk for hero slides, announcement drafts/publishing/archiving, and FAQ drafts/publishing.
- Publication dates gate scheduled public content; drafts and archived material do not appear in public querysets.
- Content publication and archive actions are recorded in an append-only audit log.
- Responsive custom CSS following the supplied UI showcase layout while preserving the existing palette; accessible dashboard reminder and keyboard-operable syllabus-level tabs.
- Light mode is the default for visitors; an explicit dark-mode choice is saved in the browser and restored on return. Responsive navigation, FAQ filters, focus styling and reduced-motion support are included.

The `/admin/` interface is retained as a technical break-glass tool; it is not the public content workflow.

## Checks

```bash
python manage.py check
python manage.py test apps.accounts.tests apps.cms.tests apps.competitions.tests
```
