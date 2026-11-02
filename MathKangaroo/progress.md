# Math Kangaroo Bangladesh — Project progress

Last updated: 2026-11-02

## Completed work — staff notifications and user management

- Added top-right toast notifications for success, error, warning, and info messages; they auto-dismiss after four seconds and can be dismissed early.
- Added a responsive, permission-gated staff account directory with search by full name, username, email, student/guardian phone, and school/institute; account editing; account-type and registration metrics; pagination; and recent account counts.
- Added staff audit events for account updates and deactivations. Deactivation removes sign-in access while retaining competition and audit history; self-deactivation and superuser deactivation are blocked.
- Added the least-privilege `Account Manager` staff group; assign it through Django Admin. A staff flag alone does not grant account-management access.
- Added regression coverage for search, account editing, permissions, history-preserving deactivation, and success-toast rendering.

## Product direction

Use `Math_Kangaroo_Bangladesh_Django_Blueprint.md` as the architecture source of truth. This is a competition platform, not only a brochure site. Preserve server-side authorization, published-content boundaries, child-data minimization, and the existing warm paper/forest visual theme. The UI showcase is a layout reference; do not replace the established palette.

## Implemented

### Platform foundation

- Django project with focused `accounts`, `audit`, `competitions`, `cms`, and `core` apps.
- Environment-driven configuration, SQLite for local development, PostgreSQL for non-debug deployments, Asia/Dhaka timezone, configurable email, and production security settings.
- Custom error pages, static assets, environment example, README, and project-specific Copilot instructions.
- Least-privilege content-editor, publisher, competition-manager, and auditor groups; append-only audit events and permission-gated staff workflows.

### Student accounts and annual participation

- Public self-registration creates a student account and registers the student for the current open Olympiad season in one transaction.
- A new student receives a generated `YY#####` participant number (for example `2700001`). That first participant number is the persistent website login username.
- Returning students log in with the participant username and password. A returning student registers for each new season separately; each annual registration has its own participant number, school and grade, while the login username does not change.
- A student can share a recovery/contact email with a sibling; email is not the account login key or a unique account field.
- Student profiles hold personal and guardian contact details. Registration records keep season-specific school, grade, division, participant number, and status history.
- Existing students who have not registered for an open current season see a dashboard reminder and a registration link. Renewal displays saved student/guardian profile details but requires the current season's school and grade again.
- Students can edit personal profile fields only during the profile-edit window configured on the season by staff/admin. The server rejects profile updates outside that window. School and grade remain part of the annual registration record.
- Participant registration sequences are allocated in the registration service. The registration creation uses a nested transaction savepoint so a uniqueness conflict is reported as a validation error without leaving the outer transaction unusable.
- Legacy accounts receive participant-style usernames through a data migration; review the migration and back up any production database before applying it.

### Competition and content

- Seasons, competition levels, season/grade divisions, registration sequences, annual registrations, versioned syllabuses, and ordered syllabus topics.
- Six editable competition levels span grades 1–12; grade/division consistency is validated server-side.
- Seeded current 2027 season and grade divisions.
- Editable site settings, homepage hero slides, categorized announcements, FAQ categories/entries, and public practice resources.
- Draft/published/archived states and future-publication gating on public content. Draft and scheduled content is excluded from public pages.
- Custom staff CMS for announcements, FAQ, hero slides, and website details. Publishing requires a separate permission; editing published content returns it to draft.
- Searchable/status-filtered/paginated content lists and a permission-gated paginated audit view. Django Admin remains the technical fallback.
- No confidential exam question bank or answer key is exposed.

### Frontend

- Public homepage now follows the showcase composition: split hero, horizontal benefits, explanatory section, current-season call to action, and recent announcements.
- Student dashboard uses a profile/sidebar layout, participant username, current-season status, registration history, and an accessible auto-open reminder dialog for an unregistered student when the current season is open.
- Returning-student renewal, profile, and registration-history pages follow the same dashboard visual system.
- Syllabus page groups published topics by competition level, with responsive, keyboard-operable tabs.
- Existing theme tokens and light/dark color palette are retained. Light mode is the default for every new visitor regardless of device preference; a visitor's explicit dark-mode selection is saved in local storage and restored on return. The UI includes responsive navigation, focus styles, skip link, reduced-motion support, and custom forms/cards.
- Hero action links are validated to local paths/fragments or HTTPS; media/resource URLs require HTTPS. Announcement images require descriptive alt text.

## Verification

- `python manage.py check` — passed.
- `python manage.py makemigrations --check --dry-run` — no model changes pending.
- `python manage.py test apps.accounts.tests apps.cms.tests apps.competitions.tests` — 33 tests passed.
- `node --check static/js/site.js` — passed.
- Pylance diagnostics for the changed account views, forms, and tests — no diagnostics.
- The test runner applies migrations to its isolated test database. Back up the local/production database before applying the participant-username data migration to a persistent database.

## Next work

1. Add a staff CMS workflow for syllabus versions/topics and public practice resources; these records are currently primarily maintained through Django Admin.
2. Add content preview, scheduling controls, validated media uploads/asset tracking, CMS-managed navigation/footer, per-page SEO/OG metadata, `sitemap.xml`, and `robots.txt`.
3. Perform full browser checks at mobile and desktop sizes in both themes; include accessibility checks for dialogs, tabs, and forms.
4. Confirm policy and product requirements for email verification, authentication throttling, password recovery for shared family email addresses, consent, and student-data export/deletion before launch.
5. Add organizations, schools, centers, coordinator assignments, and session scheduling with object-level scoping.
6. Add fees/discounts and an abstract payment gateway with verified webhooks, idempotency, and immutable payment records. Never store card data.
7. Implement validated CSV/XLSX result import preview/approval, rankings, publication controls, awards, and certificate verification.
8. Add notification templates and asynchronous email/PDF processing only when deployment needs are established; complete PostgreSQL/production integration, backups/restore, rate limiting, dependency/security review, accessibility/performance audits, and a deployment runbook.

## Local development notes

- Work from this directory; `manage.py`, the blueprint, and this file are at the Django project root.
- Local startup: activate `.venv`, then run `python manage.py migrate`, `python manage.py createsuperuser`, and `python manage.py runserver`.
- Staff groups are created after migrations. Assign groups in `/admin/`; `is_staff` alone is not application authorization.
- Default local settings use SQLite. Production fails closed unless `DJANGO_DEBUG=false`, `DJANGO_SECRET_KEY` is set, and `DB_ENGINE=postgresql` is selected.
- The current implementation seeds the 2027 season as open. Configure actual dates and profile-edit windows through the season in Django Admin before relying on them operationally.
- Before applying the username migration to an existing installation, make a database backup and review its effects on legacy users/login instructions.
- Main validation command: `python manage.py test apps.accounts.tests apps.cms.tests apps.competitions.tests`.
- Do not add generic arbitrary HTML content or expose internal exam questions. Prefer typed content, validated URLs, and explicit publication states.
