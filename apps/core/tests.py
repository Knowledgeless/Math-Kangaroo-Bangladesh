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
    "DISALLOWED_HOST_HANDLERS": (
        getattr(settings, "LOGGING", {})
        .get("loggers", {})
        .get("django.security.DisallowedHost", {})
        .get("handlers")
    ),
    "DB_PASSWORD": settings.DATABASES["default"].get("PASSWORD", ""),
    "DB_OPTIONS": settings.DATABASES["default"].get("OPTIONS", {}),
    "EMAIL_HOST_PASSWORD": settings.EMAIL_HOST_PASSWORD,
    "FILE_UPLOAD_TEMP_DIR": settings.FILE_UPLOAD_TEMP_DIR,
    "DEFAULT_STORAGE": settings.STORAGES["default"]["BACKEND"],
    "LOG_FILE": getattr(settings, "LOG_FILE", None),
    "DISALLOWED_HOST_FILTERS": (
        getattr(settings, "LOGGING", {})
        .get("loggers", {})
        .get("django.security.DisallowedHost", {})
        .get("filters")
    ),
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
        self.assertEqual(config["ALLOWED_HOSTS"], ["kangaroomathbd.org", "www.kangaroomathbd.org"])
        self.assertEqual(
            config["CSRF_TRUSTED_ORIGINS"],
            ["https://kangaroomathbd.org", "https://www.kangaroomathbd.org"],
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
        self.assertEqual(config["DEFAULT_STORAGE"], "apps.core.storage.PublicMediaStorage")
        self.assertIsNone(config["FILE_UPLOAD_TEMP_DIR"])
        self.assertEqual(config["DB_OPTIONS"], {})

    def test_https_and_hsts_options_can_be_tuned_from_the_environment(self):
        config = self.load_settings(
            {
                "DJANGO_SECURE_SSL_REDIRECT": "false",
                "DJANGO_SECURE_HSTS_SECONDS": "3600",
                "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS": "true",
                "DJANGO_SECURE_HSTS_PRELOAD": "true",
                "DJANGO_SECURE_PROXY_SSL_HEADER": "true",
                "DJANGO_ALLOWED_HOSTS": "kangaroomathbd.org",
                "DJANGO_CSRF_TRUSTED_ORIGINS": "https://kangaroomathbd.org",
            }
        )
        self.assertFalse(config["SECURE_SSL_REDIRECT"])
        self.assertEqual(config["SECURE_HSTS_SECONDS"], 3600)
        self.assertTrue(config["SECURE_HSTS_INCLUDE_SUBDOMAINS"])
        self.assertTrue(config["SECURE_HSTS_PRELOAD"])
        self.assertEqual(config["SECURE_PROXY_SSL_HEADER"], ["HTTP_X_FORWARDED_PROTO", "https"])
        self.assertEqual(config["ALLOWED_HOSTS"], ["kangaroomathbd.org"])
        self.assertEqual(config["CSRF_TRUSTED_ORIGINS"], ["https://kangaroomathbd.org"])

    def test_production_refuses_missing_secret_url_hosts_or_non_postgresql(self):
        self.assert_refused("DJANGO_SECRET_KEY", drop=("DJANGO_SECRET_KEY",))
        self.assert_refused("not URLs", {"DJANGO_ALLOWED_HOSTS": "https://kangaroomathbd.org/"})
        self.assert_refused("must use PostgreSQL", {"DB_ENGINE": "sqlite"})
        self.assert_refused("DB_ENGINE must be postgresql", {"DB_ENGINE": "mysql"})
        self.assert_refused("DB_ENGINE must be postgresql", {"DB_ENGINE": "postgress"})
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

    def test_unknown_host_errors_are_logged_but_never_emailed(self):
        log_file = self.tmp / "logs" / "django.log"
        config = self.load_settings({"DJANGO_LOG_FILE": str(log_file)})
        self.assertEqual(config["DISALLOWED_HOST_HANDLERS"], ["console", "file"])
        self.assertEqual(config["DISALLOWED_HOST_FILTERS"], ["omit_traceback"])
        self.assertTrue(log_file.parent.is_dir())
        self.assertEqual(log_file.parent.stat().st_mode & 0o777, 0o700)

    def test_log_file_path_is_resolved_like_the_other_paths(self):
        # deploy.sh tightens the log folder; it must see the real path, never
        # an unresolved "~" or ".." that could point at the home folder.
        (self.tmp / "app").mkdir()
        config = self.load_settings({"DJANGO_LOG_FILE": str(self.tmp / "app" / ".." / "logs" / "django.log")})
        self.assertEqual(config["LOG_FILE"], str((self.tmp / "logs" / "django.log").resolve()))

    def test_external_database_and_upload_folder_options(self):
        config = self.load_settings(
            {"DB_SSLMODE": "require", "DJANGO_FILE_UPLOAD_TEMP_DIR": "~/mathkangaroo-data/upload_tmp"}
        )
        self.assertEqual(config["DB_OPTIONS"], {"sslmode": "require"})
        self.assertEqual(
            config["FILE_UPLOAD_TEMP_DIR"],
            str((Path.home() / "mathkangaroo-data" / "upload_tmp").resolve()),
        )

    def test_email_ssl_and_tls_cannot_both_be_on(self):
        self.assert_refused("Set only one of EMAIL_USE_SSL", {"EMAIL_USE_SSL": "true", "EMAIL_USE_TLS": "true"})

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

    def test_env_file_values_are_taken_literally(self):
        env_file = self.tmp / ".env"
        env_file.write_text(
            "DB_PASSWORD=pa${HOME}ss\n"
            "EMAIL_HOST_PASSWORD='a b#c$d'\n",
            encoding="utf-8",
        )
        config = self.load_settings({"DJANGO_ENV_FILE": str(env_file)}, drop=("DB_PASSWORD",))
        self.assertEqual(config["DB_PASSWORD"], "pa${HOME}ss")
        self.assertEqual(config["EMAIL_HOST_PASSWORD"], "a b#c$d")

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

    def test_passenger_entry_point_always_runs_without_debug(self):
        result = self.run_probe(self.production_env, probe=PASSENGER_PROBE, drop=("DJANGO_DEBUG",))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"DEBUG": False, "callable": True})

        env_file = self.tmp / ".env"
        env_file.write_text("DJANGO_DEBUG=true\n", encoding="utf-8")
        forced = self.run_probe(
            {**self.production_env, "DJANGO_DEBUG": "true", "DJANGO_ENV_FILE": str(env_file)},
            probe=PASSENGER_PROBE,
        )
        self.assertEqual(forced.returncode, 0, forced.stderr)
        self.assertEqual(json.loads(forced.stdout), {"DEBUG": False, "callable": True})

        missing_secret = self.run_probe(
            self.production_env,
            probe=PASSENGER_PROBE,
            drop=("DJANGO_DEBUG", "DJANGO_SECRET_KEY"),
        )
        self.assertNotEqual(missing_secret.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY", missing_secret.stderr)


class OmitTracebackFilterTests(SimpleTestCase):
    def test_record_keeps_its_message_but_loses_the_traceback(self):
        import logging

        from apps.core.log_filters import OmitTraceback

        try:
            raise ValueError("boom")
        except ValueError:
            record = logging.LogRecord("x", logging.ERROR, __file__, 1, "Invalid HTTP_HOST", (), sys.exc_info())
        self.assertTrue(OmitTraceback().filter(record))
        self.assertIsNone(record.exc_info)
        self.assertEqual(logging.Formatter().format(record), "Invalid HTTP_HOST")
