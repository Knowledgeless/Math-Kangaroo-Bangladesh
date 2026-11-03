# Math Kangaroo Bangladesh — Scalable Django Website Blueprint

## 0. Executive decision

Build this as a **competition platform**, not a brochure website.

The public site should explain the competition, publish announcements, syllabus, FAQs and questions/resources. The authenticated side should support student/guardian accounts, registrations, payments, center/school operations, results and certificates. The staff side must be a **role-based CMS and operations dashboard**, so authorized non-technical staff can manage content, media, users and competition data without touching Django admin or PostgreSQL.

**Recommended stack**

- Python 3.13+
- Django 5.2 LTS-compatible architecture
- PostgreSQL
- Django Templates + HTML5
- Bootstrap 5 or a custom utility/component layer
- Vanilla JavaScript modules
- CSS variables for theming
- Redis for caching/rate limits/background-job coordination when traffic grows
- Celery for asynchronous jobs when needed
- S3-compatible object storage for media in production
- Gunicorn/Uvicorn behind Nginx or a managed platform
- Python Virtual Environment 
- GitHub Actions for tests/deployment

Do not build a React/MERN frontend just because it sounds more scalable. For this site, server-rendered Django is simpler, safer, SEO-friendly and much easier for a small operations team to maintain. Add APIs only where a real product requirement justifies them.

---

# 1. Research conclusions

## International category model

The core international structure is six competition levels covering Grades 1–12:

| Level | Grades |
|---|---|
| Pre-Ecolier | 1–2 |
| Ecolier | 3–4 |
| Benjamin | 5–6 |
| Cadet | 7–8 |
| Junior | 9–10 |
| Student/Senior | 11–12 |

Different national organizers expose these as six levels or twelve grade-specific ranking categories. Math Kangaroo India, for example, has twelve categories by grade while sharing papers between adjacent grades. This means the Bangladesh data model must NOT hard-code “six categories” or “twelve categories”. It should support both a **competition level** and a **grade-specific ranking group**.

Sources reviewed:
- https://kangaroomathbd.org/about/
- https://kangaroomathbd.org/syllabus/
- https://www.mathkangaroo.in/contest/categories
- https://mathkangaroo.ca/faq/general/contest-rules/en
- https://en.math-kangaroo.org.cn/rules
- https://kangaroomath.com.my/
- https://mathkangaroo.oasis-lms.com/Page/2026Statistics

## Bangladesh website observations

The current Bangladesh site already communicates:
- Grades 1–12
- Six levels
- Inclusive participation
- Bangladesh's national initiative
- Syllabus
- Public-facing information

The new system should preserve that simplicity while replacing hard-coded content with a structured CMS.

Do not copy another country's implementation literally. International organizers differ in exam duration, scoring, category naming, registration flow and delivery model.

---

# 2. Product architecture

Think in five layers:

```text
                 ┌─────────────────────────┐
                 │       Public Web        │
                 │ Home / Announcements    │
                 │ FAQ / Syllabus / etc.   │
                 └────────────┬────────────┘
                              │
                 ┌────────────▼────────────┐
                 │     Authentication      │
                 │ Student / Guardian      │
                 │ Staff / Coordinator     │
                 └────────────┬────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
┌─────────▼─────────┐ ┌───────▼────────┐ ┌────────▼─────────┐
│ Competition Core  │ │ CMS / Content  │ │ Operations       │
│ Years / Levels    │ │ Pages / Media  │ │ Registration     │
│ Exams / Results   │ │ FAQ / FAQ etc. │ │ Centers / Users  │
└─────────┬─────────┘ └───────┬────────┘ └────────┬─────────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              ▼
                     ┌────────────────┐
                     │ PostgreSQL     │
                     │ Redis / Storage│
                     └────────────────┘
```

---

# 3. Django project structure

Use a project package plus domain-focused apps.

```text
mathkangaroo_bd/
├── manage.py
├── config/
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── development.py
│   │   ├── production.py
│   │   └── test.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── apps/
│   ├── accounts/
│   ├── cms/
│   ├── competitions/
│   ├── registrations/
│   ├── questions/
│   ├── results/
│   ├── centers/
│   ├── payments/
│   ├── certificates/
│   ├── notifications/
│   ├── media_library/
│   ├── audit/
│   └── core/
│
├── templates/
│   ├── base.html
│   ├── includes/
│   ├── public/
│   ├── accounts/
│   ├── dashboard/
│   └── components/
│
├── static/
│   ├── css/
│   │   ├── tokens.css
│   │   ├── theme.css
│   │   ├── components.css
│   │   └── pages/
│   ├── js/
│   │   ├── theme.js
│   │   ├── navigation.js
│   │   ├── forms.js
│   │   ├── dashboard.js
│   │   └── modules/
│   └── images/
│
├── media/
├── tests/
├── docs/
├── requirements/
├── .venv
├── .env.example
├── .gitignore
└── README.md
```

Keep domain logic inside apps. Do not create a giant `views.py`, `models.py`, or `utils.py`.

---

# 4. Core data model

## 4.1 Accounts

Use a custom user model from day one.

```text
User
- id UUID
- email unique
- phone optional
- password
- first_name
- last_name
- is_active
- is_staff
- date_joined
- last_login
```

Do NOT use email as the database primary key.

Create separate profile/domain records:

```text
StudentProfile
- user OneToOne
- date_of_birth
- gender optional
- school
- grade
- district
- emergency_contact_name
- emergency_contact_phone
- photo
- guardian relationship

GuardianProfile
- user OneToOne
- occupation optional
- address
- district
- preferred_language

StaffProfile
- user OneToOne
- display_name
- organization
- role
```

For children, minimize collected personal information. Do not collect information merely because it could be useful later.

---

# 5. Roles and permissions

Do not make authorization depend only on `is_staff`.

Recommended roles:

```text
SUPER_ADMIN
NATIONAL_ADMIN
CONTENT_MANAGER
COMPETITION_MANAGER
REGISTRATION_MANAGER
CENTER_MANAGER
RESULT_MANAGER
FINANCE_MANAGER
MEDIA_MANAGER
SUPPORT_MANAGER
QUESTION_MANAGER
AUDITOR
CENTER_COORDINATOR
STUDENT
GUARDIAN
```

Use Django Groups + Permissions as the base, with object-level restrictions implemented in application logic where required.

Example:

```text
CONTENT_MANAGER
    can create/edit/publish announcements
    can edit pages
    can manage FAQ
    cannot modify payment records

RESULT_MANAGER
    can import results
    can publish results
    can issue certificates
    cannot change registration fees

CENTER_COORDINATOR
    can view/manage only their assigned center
    cannot see unrelated centers' student data
```

Never assume frontend hiding is authorization. Every sensitive action must be checked server-side.

---

# 6. CMS: the most important architectural requirement

The user requirement is:

> A non-technical person should be able to manage the website without database/backend access.

Therefore create a real CMS.

## Content entities

```text
SiteSettings
Page
PageSection
Announcement
FAQCategory
FAQ
Syllabus
SyllabusTopic
CompetitionRule
ContactInfo
SocialLink
NavigationItem
FooterSection
SEOSettings
```

### Page

```text
Page
- id
- title
- slug unique
- template_key
- status: draft/published/archived
- meta_title
- meta_description
- og_image
- created_by
- updated_by
- published_at
- created_at
- updated_at
```

### PageSection

```text
PageSection
- page FK
- section_type
- title
- subtitle
- body
- image
- button_label
- button_url
- display_order
- is_visible
- settings JSON
```

Do NOT make every page a single giant HTML field.

Use structured section types such as:

```text
HERO
TEXT
IMAGE_TEXT
STATISTICS
FEATURE_GRID
LEVEL_CARDS
TIMELINE
FAQ
ANNOUNCEMENT_LIST
CTA
TESTIMONIAL
PARTNER_LOGOS
CONTACT
CUSTOM_HTML   # restricted to trusted staff only
```

This gives staff flexible editing while preserving design consistency.

---

# 7. Media library

Do not let every model independently reinvent image uploads.

Create:

```text
MediaAsset
- id UUID
- file
- title
- alt_text
- caption
- file_type
- width
- height
- file_size
- uploaded_by
- created_at
```

Dashboard should provide:

- upload
- preview
- search
- filter
- replace
- alt text
- delete
- usage information
- image dimension validation

Hero images, logos, announcement images, certificates and gallery assets should use this system.

Production storage should be object storage, not local disk.

---

# 8. Competition model

This is where scalability matters most.

Never create fields like:

```python
is_2027 = True
```

Instead:

```text
CompetitionSeason
- id
- name
- year
- slug
- registration_open_at
- registration_close_at
- competition_date
- result_date
- status
- is_current
```

Then:

```text
CompetitionLevel
- id
- name
- code
- min_grade
- max_grade
- display_order
- description
```

Example:

```text
PRE_ECOLIER -> 1–2
ECOLIER     -> 3–4
BENJAMIN    -> 5–6
CADET       -> 7–8
JUNIOR      -> 9–10
STUDENT     -> 11–12
```

But do not hard-code these relationships permanently.

Then:

```text
CompetitionDivision
- season FK
- level FK
- grade
- ranking_group
- question_count
- duration_minutes
- max_score
- rules JSON
```

This allows future changes without migrations.

---

# 9. Registration architecture

Registration is a workflow, not a single form.

```text
Draft
  ↓
Submitted
  ↓
Pending Payment
  ↓
Payment Verified
  ↓
Confirmed
  ↓
Checked In
  ↓
Completed
  ↓
Result Published
```

Registration entities:

```text
Registration
- student
- season
- division
- center
- registration_number
- status
- fee
- discount
- final_amount
- created_at
- confirmed_at
```

Use separate:

```text
RegistrationContact
RegistrationDocument
RegistrationNote
```

Do not overwrite financial history.

---

# 10. Payments

Never store raw card information.

```text
Payment
- registration FK
- amount
- currency
- provider
- transaction_id
- status
- paid_at
- raw_response JSON
- created_at
```

Use an abstract payment service layer:

```python
PaymentGateway
    create_payment()
    verify_payment()
    refund_payment()
```

This makes future gateways replaceable.

---

# 11. Centers and schools

For nationwide expansion:

```text
Organization
School
CompetitionCenter
CenterCoordinator
CenterSession
```

A school may have multiple competition centers.

A center can have multiple sessions.

Do not assume:

```text
one school = one center
```

because that will become painful later.

---

# 12. Questions / resources

The public “Questions” page should not expose confidential upcoming exam questions.

Create:

```text
Question
QuestionSet
QuestionTopic
QuestionTag
QuestionAsset
Solution
PastPaper
```

Question lifecycle:

```text
Draft
→ Review
→ Approved
→ Published
→ Archived
```

For future online practice:

```text
PracticeAttempt
PracticeAnswer
PracticeSession
```

Never store answer keys in public HTML/JavaScript.

---

# 13. Results

Results should be versioned and importable.

```text
Result
- registration
- score
- rank_global
- rank_national
- rank_grade
- percentile
- award
- published_at
```

For bulk operations:

```text
ResultImport
- file
- uploaded_by
- status
- error_report
- created_at
```

Workflow:

```text
CSV/XLSX upload
→ validate
→ preview
→ show errors
→ approve
→ transactionally import
→ calculate rankings
→ publish
```

Never directly import unvalidated spreadsheets into production.

---

# 14. Certificates

```text
CertificateTemplate
Certificate
- registration
- certificate_number
- template
- issue_date
- verification_token
- pdf_file
- status
```

Public verification page:

```text
/verify/<certificate_number>/
```

The QR code should point to verification, not directly to a downloadable PDF.

---

# 15. Announcements

Public menu:

```text
Announcements
```

Model:

```text
Announcement
- title
- slug
- summary
- content
- cover_image
- category
- status
- published_at
- author
- pinned
- meta_title
- meta_description
```

Support:

- draft
- scheduled publish
- publish/unpublish
- pin
- archive
- featured image
- SEO

---

# 16. FAQ

Use categories:

```text
Registration
Competition
Students
Parents
Schools
Centers
Results
Certificates
Payment
```

Staff can reorder FAQs with `display_order`.

---

# 17. Syllabus

Do not store syllabus as one text blob.

```text
Syllabus
- season
- division
- title
- description

SyllabusTopic
- syllabus
- topic
- description
- display_order
```

This allows the Bangladesh committee to revise the syllabus for future seasons without destroying historical versions.

---

# 18. Main navigation

Required public navigation:

```text
Home
Announcements
FAQ
Syllabus
Questions
```

Authenticated:

```text
Login
Signup
Dashboard
Logout
```

But the UI should dynamically show:

```text
Login / Signup
```

for anonymous visitors and:

```text
Dashboard / Logout
```

for authenticated users.

Do not put both Login and Logout in the same state.

Mobile navigation must be first-class, not an afterthought.

---

# 19. Dashboard architecture

The dashboard must change based on role.

## Student

```text
My Profile
My Registration
Competition Details
Practice / Questions
Result
Certificate
Announcements
Support
```

## Guardian

```text
Children
Registrations
Payments
Results
Certificates
Announcements
Support
```

## Content Manager

```text
Pages
Sections
Announcements
FAQ
Media
Navigation
SEO
```

## Competition Manager

```text
Seasons
Levels
Divisions
Centers
Registrations
Competition Schedule
Rules
```

## Result Manager

```text
Import Results
Validate
Preview
Publish
Awards
Certificates
```

## Super Admin

Everything +:

```text
Users
Roles
Permissions
Audit Logs
System Settings
```

---

# 20. Dashboard UX

Do not make the dashboard look like Django Admin.

Build a custom interface.

Each management area should support:

```text
List
Search
Filter
Sort
Create
Edit
Preview
Publish
Archive
Delete
Bulk Actions
Audit History
```

Use confirmation dialogs for destructive actions.

Use soft-delete/archive where historical data matters.

---

# 21. Theme system

The website must have true dark/light themes.

Do NOT build two completely separate CSS files.

Use design tokens:

```css
:root {
    --color-bg: ...;
    --color-surface: ...;
    --color-text: ...;
    --color-muted: ...;
    --color-primary: ...;
    --color-secondary: ...;
    --color-accent: ...;
    --color-success: ...;
    --color-warning: ...;
    --color-danger: ...;
    --color-border: ...;
}

[data-theme="dark"] {
    --color-bg: ...;
    --color-surface: ...;
    --color-text: ...;
}
```

Store theme preference in:

1. localStorage for instant UI response
2. user profile for authenticated users

Respect `prefers-color-scheme` for first visit.

Avoid pure black and pure white.

Use colorful surfaces, gradients, badges and illustrations while maintaining WCAG contrast.

---

# 22. Visual direction

The site is for children, parents and educators.

Therefore:

### Avoid

- generic corporate blue
- flat white pages
- default Bootstrap buttons
- default Bootstrap badges
- generic dashboard cards
- excessive glassmorphism
- excessive gradients
- childish cartoon overload
- giant animations
- inaccessible text

### Use

- playful mathematical shapes
- subtle kangaroo/mathematical motifs
- colorful tags
- rounded cards
- strong typography
- geometric patterns
- illustrated empty states
- animated counters used sparingly
- colorful category cards
- friendly microcopy

The visual identity should feel:

```text
International
+ Mathematical
+ Joyful
+ Trustworthy
+ Modern
+ Child-friendly
```

Not:

```text
School ERP
```

---

# 23. Component system

Create reusable template components:

```text
components/
├── buttons/
├── badges/
├── cards/
├── forms/
├── navigation/
├── alerts/
├── modals/
├── pagination/
├── tables/
├── empty_states/
├── loaders/
├── breadcrumbs/
├── hero/
├── section_header/
└── footer/
```

Every button should be custom.

Example classes:

```text
.btn-primary
.btn-secondary
.btn-ghost
.btn-danger
.btn-success
.btn-outline
.btn-icon
```

Every badge/tag:

```text
.badge-success
.badge-warning
.badge-info
.badge-neutral
.badge-level
.badge-status
```

Never depend on Bootstrap's default visual appearance.

---

# 24. Home page

Recommended structure:

```text
Hero
↓
Competition countdown
↓
Six levels
↓
Why Math Kangaroo?
↓
How it works
↓
Important dates
↓
Participation statistics
↓
Featured announcements
↓
Syllabus preview
↓
Past questions / practice CTA
↓
Partners / organizers
↓
FAQ preview
↓
Final registration CTA
↓
Footer
```

Every section should be CMS-managed.

Hero:

```text
HeroSlide
- title
- subtitle
- image
- mobile_image
- button_1
- button_2
- active
- display_order
```

Do not hard-code the hero in HTML.

---

# 25. Announcement page

Features:

- search
- category filter
- year filter
- pagination
- pinned announcements
- featured announcement
- detail page
- related announcements

URLs:

```text
/announcements/
/announcements/<slug>/
```

---

# 26. FAQ page

Use accordion UI.

URLs:

```text
/faq/
```

Support category filtering without requiring a full page reload where practical.

---

# 27. Syllabus page

Use level cards:

```text
Pre-Ecolier
Ecolier
Benjamin
Cadet
Junior
Student
```

Then:

```text
Grade
Topics
Learning expectations
Optional downloadable PDF
```

Do not publish internal question-writing guidance as student syllabus content.

---

# 28. Questions page

Separate:

```text
Practice Questions
Past Papers
Solutions
```

Do not accidentally expose unpublished question banks.

Add permission checks to every queryset.

---

# 29. Authentication

Use:

```text
/signup/
/login/
/logout/
/password-reset/
```

For children, consider a guardian-managed registration flow.

Do not assume every young participant should independently create an unrestricted account.

Recommended model:

```text
Guardian account
    ↓
Student profile(s)
    ↓
Competition registration(s)
```

For older students, a student account can be supported subject to the organization's policy.

---

# 30. Security requirements

Mandatory:

- CSRF protection
- secure cookies
- HTTPS in production
- HSTS
- CSP
- X-Content-Type-Options
- Referrer-Policy
- clickjacking protection
- rate limiting
- login throttling
- password validation
- secure password reset
- object-level authorization
- upload validation
- file type validation
- maximum upload sizes
- audit logging
- dependency updates
- database backups
- secrets only through environment variables

Never trust:

```text
hidden input
disabled button
JavaScript validation
URL IDs
frontend role flags
```

Every important rule must be enforced server-side.

---

# 31. Child-data privacy

This is especially important.

Collect the minimum information required for:

- registration
- competition administration
- communication
- result/certificate processing

Separate sensitive/private information from public profile information.

Do not expose:

- student phone numbers
- guardian phone numbers
- addresses
- DOB
- internal registration identifiers
- private center information

in public pages.

Create explicit policies for:

```text
data retention
parent/guardian consent
result publication
photo/media consent
account deletion
data export
staff access
```

---

# 32. Audit log

Every important administrative action should be auditable.

```text
AuditLog
- actor
- action
- model_name
- object_id
- previous_data JSON
- new_data JSON
- IP
- user_agent
- timestamp
```

Track:

```text
login
logout
permission changes
content publishing
registration changes
payment changes
result import
result publication
certificate issuance
user deletion
```

This is non-negotiable for a national competition system.

---

# 33. Soft delete and historical integrity

Never casually delete:

- registrations
- payments
- results
- certificates
- audit logs
- competition seasons

Prefer:

```text
active / archived / cancelled
```

A 2027 registration must remain historically interpretable in 2030.

---

# 34. Database principles

PostgreSQL only in production.

Use:

- UUID where public identifiers are useful
- integer IDs where internal simplicity is better
- foreign keys
- unique constraints
- CheckConstraints
- indexes
- composite indexes
- DecimalField for money
- DateTimeField with timezone support
- explicit `related_name`
- appropriate `on_delete`

Do not add indexes blindly. Index actual query paths.

Examples:

```text
Announcement(status, published_at)
Registration(season, status)
Registration(center, season)
Result(season, rank_grade)
AuditLog(actor, created_at)
```

---

# 35. URL design

Use clean URLs:

```text
/
/announcements/
/announcements/<slug>/
/faq/
/syllabus/
/questions/
/questions/<slug>/
/login/
/signup/
/dashboard/
/dashboard/profile/
/dashboard/registrations/
/dashboard/results/
/dashboard/certificates/
/dashboard/content/
/dashboard/users/
/dashboard/settings/
```

Do not expose implementation details such as:

```text
/admin/catalog/product/
```

as the primary operations UI.

Django Admin can remain as a break-glass technical administration interface for trusted developers.

---

# 36. Search

Start with PostgreSQL search.

Later, if content volume becomes large:

```text
OpenSearch / Elasticsearch
```

Do not introduce Elasticsearch on day one without a demonstrated need.

---

# 37. Caching

Cache public content:

```text
homepage
syllabus
FAQ
announcement lists
published pages
```

Do NOT blindly cache:

```text
dashboard
registration status
payment status
results before publication
```

Use cache invalidation when CMS content is published/updated.

---

# 38. Background jobs

Use Celery + Redis when needed for:

```text
bulk email
certificate PDF generation
result processing
large CSV imports
image processing
scheduled publishing
notifications
```

Do not run expensive work inside a normal HTTP request.

---

# 39. Email architecture

Create notification templates:

```text
EmailTemplate
Notification
NotificationPreference
```

Events:

```text
registration submitted
payment confirmed
registration confirmed
competition reminder
result published
certificate available
password reset
announcement published
```

Never scatter email code across views.

---

# 40. Admin workflow

Example: changing homepage hero.

```text
Dashboard
→ Content
→ Homepage
→ Hero
→ Upload image
→ Add title
→ Add subtitle
→ Add CTA
→ Preview
→ Save Draft
→ Publish
```

No database access.

Example: changing syllabus.

```text
Dashboard
→ Competition
→ 2027
→ Syllabus
→ Benjamin
→ Add/Edit Topic
→ Preview
→ Publish
```

Example: managing users.

```text
Dashboard
→ Users
→ Search
→ Open User
→ View profile
→ Assign role
→ Suspend/activate
→ View audit history
```

---

# 41. Publishing model

Do not let every editor instantly change public content.

Use:

```text
DRAFT
REVIEW
PUBLISHED
ARCHIVED
```

Recommended permissions:

```text
Editor → Draft
Senior Editor → Review
Publisher → Publish
```

This prevents accidental homepage destruction.

---

# 42. Preview mode

CMS editors should have:

```text
Save Draft
Preview
Publish
Schedule
```

Preview should render the same production component templates using unpublished data.

---

# 43. SEO

Every public page needs:

```text
title
meta description
canonical URL
Open Graph image
structured data where relevant
```

Generate:

```text
sitemap.xml
robots.txt
```

Use semantic HTML.

---

# 44. Accessibility

Target WCAG 2.2 AA.

Mandatory:

- keyboard navigation
- visible focus
- sufficient contrast
- labels for form inputs
- alt text
- reduced-motion support
- screen-reader-friendly alerts
- semantic headings
- accessible modals
- no color-only status indication

Do not sacrifice accessibility for the colorful UI.

---

# 45. Performance

Target:

```text
LCP < 2.5s
CLS < 0.1
INP < 200ms
```

Use:

- responsive images
- WebP/AVIF where supported
- lazy loading
- minimal JS
- CSS optimization
- caching
- database query optimization
- `select_related`
- `prefetch_related`
- pagination

Never load 5,000 announcements into one page.

---

# 46. Testing strategy

Minimum test layers:

```text
Unit tests
Model tests
Permission tests
View tests
Form tests
CMS workflow tests
Registration workflow tests
Payment verification tests
Result import tests
Certificate verification tests
Security tests
```

Critical scenarios must have regression tests.

Example:

```text
A Center Coordinator cannot access another center's registrations.
A Content Manager cannot publish without permission.
A Student cannot access another student's result.
A cancelled registration cannot become paid through a crafted POST.
An unpublished question cannot be accessed by changing its URL.
```

---

# 47. Deployment architecture

Initial production:

```text
Internet
   ↓
CDN / WAF
   ↓
Reverse Proxy
   ↓
Django application
   ↓
PostgreSQL
   ↓
Redis
   ↓
Object Storage
```

Later:

```text
Load Balancer
   ↓
Django App 1
Django App 2
Django App 3
   ↓
Managed PostgreSQL
   ↓
Redis
   ↓
Object Storage + CDN
```

Django should remain stateless.

Never store user uploads permanently on an application server.

---

# 48. Environment configuration

Use:

```text
.env
.env.example
```

Variables:

```text
DJANGO_SECRET_KEY
DJANGO_DEBUG
DJANGO_ALLOWED_HOSTS
DATABASE_URL
REDIS_URL
EMAIL_HOST
EMAIL_PORT
EMAIL_HOST_USER
EMAIL_HOST_PASSWORD
DEFAULT_FROM_EMAIL
STORAGE_BUCKET
STORAGE_ACCESS_KEY
STORAGE_SECRET_KEY
PAYMENT_PROVIDER_KEY
SENTRY_DSN
```

Never commit secrets.

---

# 49. GitHub workflow

Branches:

```text
main
develop
feature/*
fix/*
hotfix/*
```

Pull requests should require:

```text
tests passing
linting passing
migration review
security review for auth/payment changes
```

Use conventional commits if the team is comfortable with them.

---

# 50. Suggested implementation phases

## Phase 1 — Foundation

Build:

- project settings
- custom user
- PostgreSQL
- base template
- design tokens
- dark/light theme
- navigation
- authentication
- roles/permissions
- audit logging
- error pages

## Phase 2 — Public CMS

Build:

- SiteSettings
- Page
- PageSection
- MediaAsset
- Announcement
- FAQ
- Syllabus
- Navigation
- SEO

## Phase 3 — Competition engine

Build:

- CompetitionSeason
- CompetitionLevel
- CompetitionDivision
- rules
- schedules
- centers

## Phase 4 — Registration

Build:

- guardian
- student
- registration
- fees
- coupons/discounts if required
- payment integration
- confirmation

## Phase 5 — Results

Build:

- result import
- validation
- ranking
- awards
- certificates
- public verification

## Phase 6 — Operations

Build:

- center dashboard
- staff dashboards
- bulk operations
- notifications
- reports
- exports

## Phase 7 — Practice/question platform

Build:

- question bank
- past papers
- practice mode
- solutions
- attempts
- analytics

## Phase 8 — Hardening

Do:

- security audit
- load testing
- accessibility audit
- backup restore test
- disaster recovery test
- permission matrix audit
- privacy review

---

# 51. MVP scope

Do NOT build everything simultaneously.

The first production milestone should be:

```text
Home
Announcements
FAQ
Syllabus
Questions/resources
Authentication
Student/Guardian profiles
Competition season
Levels/divisions
Registration
Dashboard
CMS
Media library
Roles/permissions
Audit log
Responsive UI
Dark/light theme
Production deployment
```

Postpone advanced online examination until the registration/public CMS system is stable.

---

# 52. What NOT to do

## Do not

- put all content in HTML templates
- make every page editable through raw HTML
- use Django Admin as the public CMS
- hard-code 2027 everywhere
- hard-code six categories into business logic
- use SQLite in production
- store uploads on ephemeral servers
- trust JavaScript for authorization
- use `if user.is_staff` for every permission
- expose Django model IDs unnecessarily
- delete historical competition records
- mix payment logic into registration views
- put business logic inside templates
- create one enormous `utils.py`
- create one enormous `models.py`
- install Elasticsearch before needing it
- build React simply because it is fashionable
- use default Bootstrap components visually
- make dark mode an afterthought
- collect unnecessary child data

---

# 53. First database relationship map

```text
User
 ├── StudentProfile
 ├── GuardianProfile
 └── StaffProfile

CompetitionSeason
 ├── CompetitionDivision
 │      └── CompetitionLevel
 ├── Syllabus
 │      └── SyllabusTopic
 ├── Registration
 │      ├── Payment
 │      ├── Result
 │      └── Certificate
 └── Center

Organization
 ├── School
 └── CompetitionCenter

CMS
 ├── Page
 │    └── PageSection
 ├── Announcement
 ├── FAQCategory
 │    └── FAQ
 ├── MediaAsset
 ├── NavigationItem
 └── SiteSettings

Question
 ├── QuestionSet
 ├── QuestionTopic
 └── Solution

AuditLog
 └── User
```

---

# 54. Copilot development rules

Create `.github/copilot-instructions.md` with these rules:

```text
1. Use Django conventions and domain-driven app separation.
2. Never bypass authorization.
3. Never put secrets in source code.
4. Never use SQLite in production.
5. Use PostgreSQL-compatible fields and constraints.
6. Use service functions/classes for complex business logic.
7. Keep templates presentation-focused.
8. Keep JavaScript modular and separate from HTML.
9. Do not use inline JavaScript.
10. Do not use default Bootstrap visual styles.
11. Every public CMS object must have a publication lifecycle.
12. Historical competition records must be immutable or auditable.
13. Every sensitive administrative mutation must create an AuditLog.
14. Use timezone-aware datetimes.
15. Use DecimalField for money.
16. Validate uploaded files.
17. Never expose unpublished content.
18. Use object-level permission checks.
19. Write tests for permissions and workflows.
20. Prefer reusable components over duplicated templates.
21. Do not introduce external infrastructure without a concrete requirement.
22. Optimize database queries with select_related/prefetch_related when justified.
23. Avoid N+1 queries.
24. Never put business rules in templates.
25. Do not silently change existing database semantics during refactoring.
26. Create migrations for model changes.
27. Review migrations before merging.
28. Use descriptive names.
29. Keep functions small.
30. Treat child privacy as a first-class requirement.
```

---

# 55. Definition of done

A feature is NOT done merely because it works locally.

It is done when:

```text
[ ] Database model exists
[ ] Migration exists
[ ] Server-side validation exists
[ ] Permission checks exist
[ ] UI exists
[ ] Mobile UI works
[ ] Dark theme works
[ ] Light theme works
[ ] Empty state exists
[ ] Loading state exists where needed
[ ] Error state exists
[ ] Audit behavior exists where relevant
[ ] Tests exist
[ ] SEO considered for public pages
[ ] Accessibility considered
[ ] Security reviewed
[ ] Query performance considered
[ ] Documentation updated
```

---

# 56. Final ruthless mentor assessment

The dangerous mistake would be to think:

> “It is only an Olympiad website, so a few Django models and templates are enough.”

That will work for the first few hundred users and then become technical debt.

The correct mental model is:

> **This is a national competition management platform with a public website attached to it.**

The public website is only the visible layer.

The real product is:

```text
Identity
+ Content
+ Competition
+ Registration
+ Centers
+ Payments
+ Results
+ Certificates
+ Permissions
+ Auditability
+ Privacy
```

Design those boundaries correctly now.

At the same time, do NOT over-engineer the first release. The architecture should be extensible, while the initial implementation remains boringly reliable.

The strongest starting stack for this project is therefore:

```text
Django
PostgreSQL
Django Templates
Custom CSS Design System
Vanilla JS
Redis (when required)
Celery (when required)
Object Storage
Python Virtual Environment
GitHub Actions
```

Build the foundation first. Then build the CMS. Then competition operations. Then registration. Then results. Only after those are stable should you build a serious online practice/exam engine.

That sequencing will save significantly more time than trying to build the “complete” system in one pass.
