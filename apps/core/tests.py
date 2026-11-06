"""Deployment-configuration regression tests.

Each case imports the settings module in a fresh interpreter with a controlled
environment, because settings are evaluated once per process.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.test import SimpleTestCase

PROJECT_ROOT = Path(settings.BASE_DIR)

SETTINGS_PROBE = """
import json
from django.conf import settings

print(json.dumps({
    "DEBUG": settings.DEBUG,
    "ALLOWED_HOSTS": settings.ALLOWED_HOSTS,
    "CSRF_TRUSTED_ORIGINS": settings.CSRF_TRUSTED_ORIGINS,
    "SECURE_SSL_REDIRECT": settings.SECURE_SSL_REDIRECT,
    "SECURE_HSTS_SECONDS": settings.SECURE_HSTS_SECONDS,
    "SECURE_HSTS_INCLUDE_SUBDOMAINS": settings.SECURE_HSTS_INCLUDE_SUBDOMAINS,
    "SECURE_HSTS_PRELOAD": settings.SECURE_HSTS_PRELOAD,
    "SECURE_PROXY_SSL_HEADER": settings.SECURE_PROXY_SSL_HEADER,
    "SESSION_COOKIE_SECURE": settings.SESSION_COOKIE_SECURE,
    "CSRF_COOKIE_SECURE": settings.CSRF_COOKIE_SECURE,
    "DATABASE": {
        key: str(value)
        for key, value in settings.DATABASES["default"].items()
        if key in {"ENGINE", "NAME", "HOST", "PORT", "OPTIONS"}
    },
    "STATICFILES_BACKEND": settings.STORAGES["staticfiles"]["BACKEND"],
    "MIDDLEWARE": settings.MIDDLEWARE,
    "STATIC_ROOT": str(settings.STATIC_ROOT),
    "MEDIA_ROOT": str(settings.MEDIA_ROOT),
    "PRIVATE_MEDIA_ROOT": str(settings.PRIVATE_MEDIA_ROOT),
    "EMAIL_USE_SSL": settings.EMAIL_USE_SSL,
    "EMAIL_USE_TLS": settings.EMAIL_USE_TLS,
    "ADMINS": settings.ADMINS,
    "LOG_HANDLERS": sorted(getattr(settings, "LOGGING", {}).get("handlers", {})),
}))
"""

PASSENGER_PROBE = """
import json
import passenger_wsgi
from django.conf import settings

print(json.dumps({"DEBUG": settings.DEBUG, "callable": callable(passenger_wsgi.application)}))
"""


class DeploymentSettingsTests(SimpleTestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp = Path(directory.name)
        self.production_env = {
            "DJANGO_ENV_FILE": str(self.tmp / "missing.env"),
            "DJANGO_DEBUG": "false",
            "DJANGO_SECRET_KEY": "test-only-" + "s" * 50,
            "DJANGO_ALLOWED_HOSTS": "mathkangaroo.example.org,www.mathkangaroo.example.org",
            "DB_ENGINE": "postgresql",
            "DB_NAME": "mk_db",
            "DB_USER": "mk_user",
            "DB_PASSWORD": "secret",
            "DJANGO_STATIC_ROOT": str(self.tmp / "public_html" / "static"),
            "DJANGO_MEDIA_ROOT": str(self.tmp / "public_html" / "media"),
            "DJANGO_PRIVATE_MEDIA_ROOT": str(self.tmp / "private_media"),
        }

    def run_probe(self, overrides, probe=SETTINGS_PROBE, drop=()):
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("DJANGO_", "DB_", "EMAIL_", "DEFAULT_FROM_EMAIL", "SERVER_EMAIL"))
        }
        environment["DJANGO_SETTINGS_MODULE"] = "MathKangaroo.settings"
        environment.update(overrides)
        for key in drop:
            environment.pop(key, None)
        return subprocess.run(
            [sys.executable, "-c", probe],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def load_settings(self, overrides=None, drop=()):
        result = self.run_probe({**self.production_env, **(overrides or {})}, drop=drop)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def assert_refused(self, message, overrides=None, drop=()):
        result = self.run_probe({**self.production_env, **(overrides or {})}, drop=drop)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("ImproperlyConfigured", result.stderr)
        self.assertIn(message, result.stderr)

    def test_production_settings_are_secure_by_default(self):
        config = self.load_settings()
        self.assertFalse(config["DEBUG"])
        self.assertEqual(
            config["ALLOWED_HOSTS"],
            ["mathkangaroo.example.org", "www.mathkangaroo.example.org"],
        )
        self.assertTrue(config["SECURE_SSL_REDIRECT"])
        self.assertTrue(config["SESSION_COOKIE_SECURE"])
        self.assertTrue(config["CSRF_COOKIE_SECURE"])
        self.assertEqual(config["SECURE_HSTS_SECONDS"], 31_536_000)
        self.assertFalse(config["SECURE_HSTS_INCLUDE_SUBDOMAINS"])
        self.assertFalse(config["SECURE_HSTS_PRELOAD"])
        self.assertIsNone(config["SECURE_PROXY_SSL_HEADER"])
        self.assertEqual(config["DATABASE"]["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(config["DATABASE"]["PORT"], "5432")
        self.assertEqual(
            config["STATICFILES_BACKEND"],
            "whitenoise.storage.CompressedManifestStaticFilesStorage",
        )
        self.assertEqual(config["MIDDLEWARE"][1], "whitenoise.middleware.WhiteNoiseMiddleware")
        self.assertEqual(config["STATIC_ROOT"], str((self.tmp / "public_html" / "static").resolve()))
        self.assertEqual(config["PRIVATE_MEDIA_ROOT"], str((self.tmp / "private_media").resolve()))
        self.assertIn("console", config["LOG_HANDLERS"])

    def test_https_and_hsts_options_can_be_tuned_from_the_environment(self):
        config = self.load_settings(
            {
                "DJANGO_SECURE_SSL_REDIRECT": "false",
                "DJANGO_SECURE_HSTS_SECONDS": "3600",
                "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS": "true",
                "DJANGO_SECURE_HSTS_PRELOAD": "true",
                "DJANGO_SECURE_PROXY_SSL_HEADER": "true",
                "DJANGO_CSRF_TRUSTED_ORIGINS": "https://mathkangaroo.example.org",
            }
        )
        self.assertFalse(config["SECURE_SSL_REDIRECT"])
        self.assertEqual(config["SECURE_HSTS_SECONDS"], 3600)
        self.assertTrue(config["SECURE_HSTS_INCLUDE_SUBDOMAINS"])
        self.assertTrue(config["SECURE_HSTS_PRELOAD"])
        self.assertEqual(config["SECURE_PROXY_SSL_HEADER"], ["HTTP_X_FORWARDED_PROTO", "https"])
        self.assertEqual(config["CSRF_TRUSTED_ORIGINS"], ["https://mathkangaroo.example.org"])

    def test_production_refuses_missing_secret_hosts_or_sqlite(self):
        self.assert_refused("DJANGO_SECRET_KEY", drop=("DJANGO_SECRET_KEY",))
        self.assert_refused("DJANGO_ALLOWED_HOSTS", drop=("DJANGO_ALLOWED_HOSTS",))
        self.assert_refused("DB_ENGINE=postgresql", {"DB_ENGINE": "sqlite"})
        self.assert_refused("DB_ENGINE must be", {"DB_ENGINE": "postgress"})
        self.assert_refused("whole number", {"DJANGO_SECURE_HSTS_SECONDS": "one year"})

    def test_private_media_must_not_be_web_served(self):
        self.assert_refused(
            "must not be inside",
            {"DJANGO_PRIVATE_MEDIA_ROOT": str(self.tmp / "public_html" / "media" / "private")},
        )
        self.assert_refused(
            "outside public_html",
            {"DJANGO_PRIVATE_MEDIA_ROOT": str(self.tmp / "public_html" / "private")},
        )

    def test_mysql_fallback_uses_utf8mb4_and_strict_mode(self):
        config = self.load_settings({"DB_ENGINE": "mysql"})
        database = config["DATABASE"]
        self.assertEqual(database["ENGINE"], "django.db.backends.mysql")
        self.assertEqual(database["PORT"], "3306")
        self.assertIn("utf8mb4", database["OPTIONS"])
        self.assertIn("STRICT_TRANS_TABLES", database["OPTIONS"])

    def test_cpanel_mail_and_admin_settings(self):
        config = self.load_settings(
            {
                "EMAIL_USE_SSL": "true",
                "DJANGO_ADMINS": "Site Admin <admin@example.org>, ops@example.org, not-an-address",
            }
        )
        self.assertTrue(config["EMAIL_USE_SSL"])
        self.assertFalse(config["EMAIL_USE_TLS"])
        self.assertEqual(
            config["ADMINS"],
            [["Site Admin", "admin@example.org"], ["", "ops@example.org"]],
        )

    def test_env_file_fills_values_without_overriding_the_process_environment(self):
        env_file = self.tmp / ".env"
        env_file.write_text(
            "DJANGO_ALLOWED_HOSTS=from-file.example.org\n"
            'DEFAULT_FROM_EMAIL="Math Kangaroo Bangladesh <no-reply@example.org>"\n'
            "DJANGO_SECURE_HSTS_SECONDS=60\n",
            encoding="utf-8",
        )
        config = self.load_settings(
            {"DJANGO_ENV_FILE": str(env_file), "DJANGO_SECURE_HSTS_SECONDS": "120"},
            drop=("DJANGO_ALLOWED_HOSTS",),
        )
        self.assertEqual(config["ALLOWED_HOSTS"], ["from-file.example.org"])
        self.assertEqual(config["SECURE_HSTS_SECONDS"], 120)

    def test_development_defaults_are_unchanged_without_configuration(self):
        result = self.run_probe({"DJANGO_ENV_FILE": str(self.tmp / "missing.env")})
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(result.stdout)
        self.assertTrue(config["DEBUG"])
        self.assertEqual(config["DATABASE"]["ENGINE"], "django.db.backends.sqlite3")
        self.assertNotIn("whitenoise.middleware.WhiteNoiseMiddleware", config["MIDDLEWARE"])

    def test_passenger_entry_point_fails_safe_to_production_mode(self):
        result = self.run_probe(self.production_env, probe=PASSENGER_PROBE, drop=("DJANGO_DEBUG",))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"DEBUG": False, "callable": True})

        missing_secret = self.run_probe(
            self.production_env,
            probe=PASSENGER_PROBE,
            drop=("DJANGO_DEBUG", "DJANGO_SECRET_KEY"),
        )
        self.assertNotEqual(missing_secret.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY", missing_secret.stderr)
