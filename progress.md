# Math Kangaroo Bangladesh — Project progress

Last updated: 2026-11-07

## Completed work — required-field marks, automatic slugs, title case and toast countdown

### Required fields are marked

- Every form field label now shows a small red `*` when the field is required, through one
  shared snippet and the `.required-mark` style. Optional fields show nothing, so
  "Student phone (optional)" and the cover-image and search-engine fields stay bare.
- Covers the content desk and all of its pages (announcement, FAQ, syllabus, question paper,
  About, website details), signup, and the remaining account forms (login, profile, annual
  registration, staff user, password reset) so the whole site reads the same way.
- The announcement and About photo rows sit under an "optional photos" heading but their
  fields are required once a row is started. Their help text now says exactly that, so the
  new stars do not read as "you must add a photo".

### Slug is no longer asked for

- Removed the slug field from the announcement form. `Announcement.save()` builds one from the
  title on first save only, so an address that is already published never moves when the title
  is later edited.
- Repeated titles get `-2`, `-3` and so on. A title with no Latin letters (Bengali, for
  example) slugifies to an empty string, so it falls back to `announcement`, `announcement-2`.
- The content desk still shows each announcement's slug beneath its title, as it is the page's
  web address.

### Titles read in title case

- Done with CSS `text-transform: capitalize` on headings (`h1`–`h6`) plus content titles in the
  content desk tables and lists, related-story links, and the homepage benefit and registration
  detail titles.
- CSS was chosen over Django's `title` filter, which lowercases the rest of every word and
  would turn "PDF" into "Pdf" and "FAQ" into "Faq". CSS capitalize leaves the rest of each word
  alone and does not touch the saved text. Checked in Chromium: `PDF`, `FAQ`, `Let's` and
  `Écolier` all survive.
- For that reason the `{{ announcement.title | title }}` filter added by hand to
  `announcement_detail.html` was replaced with the plain value; the shared CSS now covers it.
- Deliberately not applied to every `<strong>`, because those also carry data such as email
  addresses, usernames and school names, which must stay as entered. `.no-title-case` is
  available to opt a heading out.

### Toast notifications count down

- Each toast now has a bar along its bottom edge that shrinks over the four seconds before the
  toast dismisses itself. It takes `currentColor`, so it is green, red, amber or blue to match
  a success, error, warning or info message.
- The four-second figure lives in `site.js` only and is passed to the CSS as
  `--toast-duration`, so the bar and the timer cannot drift apart. The bar holds still under
  `prefers-reduced-motion`.

### Verification

- 99 application tests, including new coverage for the required marks on the content desk and
  signup, slug generation (from title, duplicates, non-Latin titles, stability on rename), and
  a countdown bar on each of the four toast types.
- Rendered in headless Chromium: signup, homepage, announcements, the announcement form, the
  content desk tables, and the four toast types in both light and dark themes.
- The two previously recorded `accounts` test failures are unchanged.

## Completed work — birthdate year/month selection and content desk row actions

### Date of birth picker

The signup calendar only had previous/next month arrows, so reaching a student's birth year
meant roughly 150 clicks.

- The month name is now a month dropdown and a year dropdown, so a birth date is three
  choices. The arrows still step one month at a time.
- The year list covers the current year back 100 years, newest first, because a student's
  birth year sits near the top.
- Future dates stay unreachable: months after the current one are disabled while the current
  year is shown, and the dropdowns cannot move past this month. The shown month is clamped
  into range, so a saved date outside the list still opens sensibly.
- Verified in a real DOM with jsdom: 12 months, 101 years, picking year then month then day
  fills the field as `YYYY-MM-DD`, future months are disabled, and reopening returns to the
  saved month. Also rendered in headless Chromium to confirm the layout.

### Content desk row actions

Every row in the content desk now offers edit, archive and delete as icon-only controls
(pencil, archive box, red trash). The wording lives in `aria-label` and `title` only.

- Added the missing actions: archive and delete for FAQs, archive and delete for syllabuses,
  delete for announcements, delete for question papers.
- All six new views are POST-only and permission-gated (`delete_announcement`, `change_faq`,
  `delete_faq`, `change_syllabus`, `delete_syllabus`, `delete_questionpaper`), matching the
  existing archive views. Each one writes an audit event; for deletes the event is written
  first, so the audit trail outlives the record.
- Deleting also removes the uploaded files: announcement images, and a question paper's PDF
  from private storage. Deleting a syllabus removes its topics but keeps its competition
  division.
- Archive is hidden on rows that are already archived. Delete asks for confirmation first.
- `.table-actions` no longer flattens `.action-icon` controls into plain text links, so the
  icon buttons keep their pill styling; `.cms-actions` lays them out in a row.
- Verified: 54 CMS tests and 95 application tests, plus headless Chromium renders of the
  table rows and the FAQ list rows.

## Completed work — announcement image rows without a file

Visiting `/announcements/` raised `ValueError: The 'image' attribute has no file associated with it.`
An `AnnouncementImage` row had been saved with an empty `image`, and the public templates
asked that row for `image.url`.

- **Cause:** the announcement image field was `required=False`, so a row with alt text but no
  chosen file was accepted and stored with an empty `image`. Both the content desk and the
  Django Admin inline could create one.
- The image field is now required. An existing row keeps its current file when the announcement
  is edited without a new upload, and a completely blank extra row is still ignored, so saving an
  announcement with no images works as before.
- The public announcement list, homepage and announcement detail views prefetch through
  `_public_images()`, which excludes rows with no file. The About page filters its gallery the
  same way.
- The public templates also check `image.image` before reading `image.url`, so a row without a
  file can never raise again if a future view forgets to filter.
- Existing empty rows stay in the database and are simply not rendered. Because the field is now
  required, opening such an announcement in the content desk or Admin asks for a file for that
  row, or for the row to be removed, before it will save.
- Verified: 49 CMS tests, 90 application tests, and the live `/`, `/announcements/`,
  `/announcements/<slug>/` and `/about/` pages against the development database, which still
  holds one such empty row.

Note: run the suite as `python manage.py test apps`. Plain `manage.py test` also discovers the
project a second time as `MathKangaroo.apps.*` and reports three import errors that are a test
loader artifact, not real failures.

## Completed work — cPanel deployment for https://kangaroomathbd.org/

### Production settings

- `MathKangaroo/settings.py` reads the environment plus an optional `.env` file. Values are taken literally, and the real environment wins over the file.
- Production defaults:
  - allowed hosts `kangaroomathbd.org` and `www.kangaroomathbd.org`, with matching `https://` CSRF origins;
  - PostgreSQL, with an optional `DB_SSLMODE`.
- Production refuses to start when:
  - the secret key is missing;
  - a host is given as a URL;
  - the database is not PostgreSQL;
  - both email SSL and TLS are enabled;
  - private media sits inside a web-served folder.
- `passenger_wsgi.py` is the cPanel startup file. It always forces `DEBUG` off for the live site.
- Static files use WhiteNoise's hashed manifest in production. The vendored bootstrap-icons CSS no longer points to a missing `.woff` file.
- Logging:
  - production logs go to a file;
  - unknown-host requests are logged as one line and never emailed;
  - server errors are emailed to `DJANGO_ADMINS`.

### Uploads and question papers

- **Security fix:** question-paper PDFs now use `PrivateMediaStorage` under `DJANGO_PRIVATE_MEDIA_ROOT`, outside `public_html`. Draft PDFs were previously downloadable at `/media/question-papers/<name>`. Migration `cms.0010_questionpaper_private_storage` changes no database schema.
- The `/media/` fallback view refuses `question-papers/` and hidden files, including when dot segments are used.
- Public uploads keep only their last extension (`shell.php.jpg` is saved as `shell_php.jpg`), so cPanel's PHP handlers can never run an uploaded image.

### Deployment files in `deploy/cpanel/`

- `README.md` is the step-by-step runbook.
- `production.env.example` is the `.env` template with the domain, PostgreSQL and mail settings filled in.
- `deploy.sh`:
  - checks the `.env` file;
  - installs packages;
  - connects to the database and enforces PostgreSQL 14+;
  - creates private folders without ever locking the home folder or document root;
  - runs `check --deploy`;
  - backs up the database before migrations;
  - migrates;
  - collects static files and installs the `.htaccess` rules;
  - restarts the app.
- `backup.sh` serves deploys and the nightly cron job. It checks the `pg_dump` and server versions.
- `.htaccess` templates:
  - one canonical `https://kangaroomathbd.org/` (www and HTTP redirect there in one step, with AutoSSL paths exempt);
  - no directory listings;
  - script-like media files refused wherever the extension appears in the name;
  - year-long cache headers for hashed static files.

### Verification

- Test suite on Python 3.10 with real PostgreSQL 16/18.
- Repeated end-to-end `deploy.sh` rehearsals in a simulated cPanel account, covering:
  - PostgreSQL 13 refusal;
  - a wrong password;
  - first deploy;
  - rerun;
  - unsafe log paths;
  - backup and restore.
- `.htaccess` behaviour on real Apache 2.4, including a cPanel-style PHP handler for the double-extension test.
- shellcheck on both scripts.
- Not tested: real LiteSpeed and real Passenger, which are unavailable locally.

### Before going live

- Confirm the host's PostgreSQL is 14 or newer; Django 5.2 requires it, and stock cPanel often ships 10 or 13. See the runbook.
- Two `accounts` tests were already failing before this work and still fail:
  - `test_registration_statistics_use_live_data_and_staff_shell`;
  - `test_staff_user_dashboard_searches_all_requested_fields_and_shows_stats`.

## Completed work — locally bundled site typography

- Downloaded and bundled the Bricolage Grotesque variable font (weights 200–800) and all nine Poppins weights (100–900), with both SIL Open Font Licenses.
- Removed the remote Google Fonts dependency and configured local `@font-face` declarations so headings/navigation use Bricolage Grotesque and body text/controls use Poppins.
- Verified local static-file resolution, Django checks, and browser-computed body, heading, and navigation fonts; confirmed the browser loads both font families from `/static/fonts/`.

## Completed work — sitewide typography refresh

- Added Bricolage Grotesque for headings and primary navigation and Poppins for body copy and controls, loaded through the shared base template.
- Tuned the shared heading scale and body line-height for the updated typefaces without changing light or dark theme colors.
- Confirmed both font families are available; Django system checks and `git diff --check` pass.

## Completed work — CMS category dropdown visibility and styling

- Added a custom category picker that opens on hover, focus, or click, with keyboard selection, styled season groups, and a visible selected-category label.
- Kept the form's existing duplicate-syllabus protection. The picker shows already-assigned categories with direct edit links instead of appearing empty when all categories are taken.
- Hid the underlying submitted select so it no longer renders as a second visible control; the custom menu also opens on hover/focus without waiting for JavaScript.
- Added regression assertions for the single visible picker, populated categories, and existing-syllabus entries.
- Verified the category-picker regression test, Django system checks, JavaScript syntax, and `git diff --check`.

## Completed work — paired-category syllabus picker and public redesign

- Changed the CMS syllabus picker to offer each season/category once, with its combined two-grade range, instead of separate grade options.
- Updated the public syllabus page to foreground categories and seasons, display each category's saved syllabus description and topics with its paired grade range, and expand the content area with responsive cards, transitions, and reduced-motion support through the site's shared accessibility rule.
- Styled syllabus and topic titles in title case without changing the saved text.
- Added regression assertions for the paired-grade CMS category picker.
- Verified the category picker (including combined-grade labels, no duplicate category options, and editability), public syllabus/topic rendering, Django system checks, and `git diff --check`.

## Completed work — About sample layout and managed image uploads

- Reworked the public About page to use the saved About copy as its heading and section text, styled after `static/images/about_sample.png`; no placeholder story text or stock photo is shown.
- About paragraphs are justified. Added repeatable About-page photo rows with alt text, ordering, preview, and removal in the content desk; only uploaded photos appear publicly.
- Added repeatable announcement image rows with alt text, ordering, preview, and removal in the content desk. Every new announcement image must be exactly 1200 × 630 pixels and smaller than 300 KB.
- Announcement images appear on public announcement cards, the homepage cards, and announcement details. Existing external cover-image fields remain available as a fallback.
- Added and applied CMS migration `0009_aboutpageimage_announcementimage`.
- Verified 63 account/CMS/competition tests, Django system checks, migration consistency, JavaScript syntax, and the live About page text alignment.

## Completed work — logo sizing and password visibility

- Constrained the header logo to a consistent 140 × 64 px area while preserving its image proportions.
- Added accessible eye controls to password inputs so users can show or hide entered passwords across account forms.

## Completed work — editable About, syllabus, practice PDFs and birthdate calendar

- Added a public About page with editable title, introduction and body content, managed from the custom staff content desk.
- Added frontend syllabus management by season and grade, including editable topic rows and separate draft/publish permissions.
- Added content-desk PDF upload, edit and archive workflows with year/category metadata, 20 MB size and PDF-signature validation, publication gating, and attachment-only downloads.
- Added public Practice-page year and category filters, including all-years/all-categories options and matching download buttons above existing practice resources.
- Replaced the browser-native birthdate field picker with a branded, keyboard-operable calendar that matches the site's colors and prevents selecting future dates.
- Verified all 55 application tests, Django system checks, migration consistency, and JavaScript syntax.

## Completed work — hero slider transitions

- Added five distinct smooth entrance effects to the homepage hero images. Effects rotate by slide position, so later slides use varied transitions without additional configuration.
- Replays the selected entrance effect on each slide change, including manual navigation; existing four-second autoplay and reduced-motion behavior remain unchanged.
- Verified JavaScript syntax, carousel advancement and looping, and the CMS hero-slider regression tests.

## Completed work — dashboard redesign and notification verification

- Kept four-second, top-right light-background notifications and verified distinct success, error, warning and info styles; errors use alert semantics.
- Replaced the staff landing page with a responsive, custom-designed operations dashboard patterned after `Math Kangaroo Bangladesh Dashboard.png`, using the established green/cream/lilac/coral palette for navigation, registration charts, level breakdown, quick actions, and activity.
- Dashboard totals and graphs use live account, competition-registration and audit data, and each panel/action is gated by its Django permission. The Account Manager group now has read-only registration/season access for dashboard summaries.
- Redesigned student dashboard/profile pages around the provided profile reference: participant identity, account details, institute/category, and year-by-year participation. Students see only their own profile and registration records.
- Kept dashboard actions on custom frontend pages; competition registration totals and trends link to the custom overview instead of the default Django Admin interface.
- Added regression tests for all four toast types, staff permissions and live dashboard data, plus retained profile-edit and annual-registration coverage.

## Completed work — staff notifications and user management

- Added top-right toast notifications for success, error, warning, and info messages; they auto-dismiss after four seconds and can be dismissed early.
- Added a responsive, permission-gated staff account directory with search by full name, username, email, student/guardian phone, and school/institute; account editing; account-type and registration metrics; pagination; and recent account counts.
- Added staff audit events for account updates and deactivations. Deactivation removes sign-in access while retaining competition and audit history; self-deactivation and superuser deactivation are blocked.
- Added the least-privilege `Account Manager` staff group; assign it through Django Admin. A staff flag alone does not grant account-management access.
- Added regression coverage for search, account editing, permissions, history-preserving deactivation, and success-toast rendering.

## Completed work — staff analytics, persistent navigation and feedback

- Added a server-permission-protected registration-statistics page using current database records: all-season registrations, unique participants and institutions, current-season new/returning participants, category and grade breakdowns, district and institution summaries, and a 30-day registration trend.
- Kept PDF-referenced gender and upazila charts out of the report because those fields are not collected; the page explains that limitation rather than inventing values.
- Added a shared staff dashboard shell and persistent permission-aware sidebar to staff dashboard, analytics, user directory/edit, CMS, and audit pages. Aligned student registration history with the existing student sidebar.
- Added paused-typing live search to staff user/content/audit directories, icon-only search and user actions with accessible labels, and light custom action-button backgrounds.
- Invalid account, CMS, and site-settings submissions now queue a warning toast alongside inline field errors; successful changes continue to use their existing success toasts.
- Added regression tests for statistics values, district data, permission denial and invalid-form toast feedback.

## Product direction

Use `Math_Kangaroo_Bangladesh_Django_Blueprint.md` as the architecture source of truth. This is a competition platform, not only a brochure site. Preserve server-side authorization, published-content boundaries, child-data minimization, and the existing warm paper/forest visual theme. The UI showcase is a layout reference; do not replace the established palette.

## Implemented

### Platform foundation

- Django project with focused `accounts`, `audit`, `competitions`, `cms`, and `core` apps.
- Environment-driven configuration (`.env` supported), SQLite for local development, PostgreSQL 14+ for production, Asia/Dhaka timezone, configurable email, production security settings, and the cPanel deployment kit in `deploy/cpanel/`.
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
- `python manage.py test apps.core.tests apps.accounts.tests apps.cms.tests apps.competitions.tests` — 85 tests; 83 pass. The 2 `accounts` failures predate the deployment work (see above).
- `node --check static/js/site.js` — passed.
- CMS migration `0009_aboutpageimage_announcementimage` — applied to the local database.
- Updated dashboard templates compiled successfully.
- The test runner applies migrations to its isolated test database. Back up the local/production database before applying the participant-username data migration to a persistent database.

## Next work

1. Add a staff CMS workflow for syllabus versions/topics and public practice resources; these records are currently primarily maintained through Django Admin.
2. Add content preview, scheduling controls, validated media uploads/asset tracking, CMS-managed navigation/footer, per-page SEO/OG metadata, `sitemap.xml`, and `robots.txt`.
3. Perform full browser checks at mobile and desktop sizes in both themes; include accessibility checks for dialogs, tabs, and forms.
4. Confirm policy and product requirements for email verification, authentication throttling, password recovery for shared family email addresses, consent, and student-data export/deletion before launch.
5. Add organizations, schools, centers, coordinator assignments, and session scheduling with object-level scoping.
6. Add fees/discounts and an abstract payment gateway with verified webhooks, idempotency, and immutable payment records. Never store card data.
7. Implement validated CSV/XLSX result import preview/approval, rankings, publication controls, awards, and certificate verification.
8. Add notification templates and asynchronous email/PDF processing only when deployment needs are established; add rate limiting, an off-server backup and restore drill, dependency/security review, and accessibility/performance audits. The PostgreSQL production setup, backups and cPanel runbook are done.

## Local development notes

- Work from this directory; `manage.py`, the blueprint, and this file are at the Django project root.
- Local startup: activate `.venv`, then run `python manage.py migrate`, `python manage.py createsuperuser`, and `python manage.py runserver`.
- Staff groups are created after migrations. Assign groups in `/admin/`; `is_staff` alone is not application authorization.
- Default local settings use SQLite with DEBUG on. Production (any `DJANGO_DEBUG=false` process; `passenger_wsgi.py` always forces it) fails closed without `DJANGO_SECRET_KEY` and PostgreSQL. Deployment is described in `deploy/cpanel/README.md`.
- The current implementation seeds the 2027 season as open. Configure actual dates and profile-edit windows through the season in Django Admin before relying on them operationally.
- Before applying the username migration to an existing installation, make a database backup and review its effects on legacy users/login instructions.
- Main validation command: `python manage.py test apps.core.tests apps.accounts.tests apps.cms.tests apps.competitions.tests`.
- Do not add generic arbitrary HTML content or expose internal exam questions. Prefer typed content, validated URLs, and explicit publication states.
