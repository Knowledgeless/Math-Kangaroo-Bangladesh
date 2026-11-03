# Project instructions

1. Use Django conventions and domain-focused apps.
2. Enforce authorization on the server for every sensitive action.
3. Keep secrets in environment configuration, never source code.
4. Use PostgreSQL in production; SQLite is for local development and tests only.
5. Put non-trivial business rules in models, forms or services, not templates.
6. Keep templates presentation-focused and JavaScript in static modules.
7. Preserve the custom design system; do not rely on default Bootstrap styling.
8. Keep public content behind explicit publication-state and schedule checks.
9. Preserve competition, payment, result, certificate and audit history.
10. Use timezone-aware datetimes and DecimalField for money.
11. Validate user input and uploads on the server.
12. Never publish confidential questions or expose answer keys to the browser.
13. Add regression tests for permissions, public visibility and workflow transitions.
14. Treat child privacy and least-privilege staff access as product requirements.
15. Add migrations for schema changes and review generated migrations.
