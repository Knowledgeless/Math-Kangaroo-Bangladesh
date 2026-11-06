import os
from email.utils import parseaddr
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


# --- Environment -----------------------------------------------------------
# Values come from the process environment first. A .env file in the project
# root (or the file named by DJANGO_ENV_FILE) fills in anything not already
# set, so cPanel "Setup Python App" variables always win over the file, and
# management commands run from the cPanel Terminal see the same configuration
# as the Passenger web process.

ENV_FILE = Path(os.environ.get("DJANGO_ENV_FILE") or BASE_DIR / ".env")
if ENV_FILE.is_file():
    from dotenv import load_dotenv

    load_dotenv(ENV_FILE, override=False)


def env(name, default=""):
    value = os.environ.get(name)
    return default if value is None or not value.strip() else value.strip()


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    value = env(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError as error:
        raise ImproperlyConfigured(f"{name} must be a whole number; got {value!r}.") from error


def env_list(name, default=""):
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


def env_path(name, default):
    value = env(name)
    return Path(value).expanduser().resolve() if value else default


# --- Core ------------------------------------------------------------------

# Local development runs with DEBUG on. The deploy entry points
# (passenger_wsgi.py, deploy/cpanel/deploy.sh and backup.sh) force
# DJANGO_DEBUG=false, so the live site never runs with DEBUG.
DEBUG = env_bool("DJANGO_DEBUG", True)
SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be configured when DEBUG is disabled.")
    SECRET_KEY = "development-only-not-for-production"

# The live site is https://kangaroomathbd.org/ (www redirects there via
# .htaccess). Set DJANGO_ALLOWED_HOSTS only if the domain changes.
PRODUCTION_HOSTS = ["kangaroomathbd.org", "www.kangaroomathbd.org"]
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS") or (
    PRODUCTION_HOSTS if not DEBUG else ["localhost", "127.0.0.1", "[::1]"]
)
if any("://" in host or "/" in host for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS takes host names such as kangaroomathbd.org, not URLs."
    )
# Forms are posted from these origins; defaults to https:// + each host.
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS") or (
    []
    if DEBUG
    else [f"https://{host}" for host in ALLOWED_HOSTS if host != "*" and not host.startswith(".")]
)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'apps.accounts',
    'apps.audit',
    'apps.competitions',
    'apps.cms',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'apps.core.middleware.SecurityHeadersMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
if not DEBUG:
    # Serves collected static files when the web server does not (runserver
    # already serves them in development).
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

ROOT_URLCONF = 'MathKangaroo.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.cms.context_processors.site_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'MathKangaroo.wsgi.application'


# --- Database --------------------------------------------------------------
# Production uses PostgreSQL (cPanel > PostgreSQL Databases). SQLite is only
# for local development; production refuses to start with anything else.

DB_ENGINE = env("DB_ENGINE", "sqlite" if DEBUG else "postgresql").lower()
DB_CONN_MAX_AGE = env_int("DB_CONN_MAX_AGE", 60)

if DB_ENGINE in {"postgresql", "postgres"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", "mathkangaroo"),
            "USER": env("DB_USER"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "localhost"),
            "PORT": env("DB_PORT", "5432"),
            "CONN_MAX_AGE": DB_CONN_MAX_AGE,
            "CONN_HEALTH_CHECKS": True,
        }
    }
elif DB_ENGINE in {"sqlite", "sqlite3"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    raise ImproperlyConfigured(
        f"DB_ENGINE must be postgresql (or sqlite for local development); got {DB_ENGINE!r}."
    )

if not DEBUG and DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured("Production deployments must use PostgreSQL (DB_ENGINE=postgresql).")


# --- Authentication --------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:dashboard"
LOGOUT_REDIRECT_URL = "home"


# --- Email -----------------------------------------------------------------
# cPanel mailboxes usually use port 465 with SSL or port 587 with STARTTLS.

EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", not EMAIL_USE_SSL)
EMAIL_TIMEOUT = env_int("EMAIL_TIMEOUT", 20)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "Math Kangaroo Bangladesh <no-reply@mathkangaroo.bd>")
SERVER_EMAIL = env("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
# Comma-separated "Name <email>" entries that receive server-error emails.
ADMINS = [parseaddr(entry) for entry in env_list("DJANGO_ADMINS") if "@" in parseaddr(entry)[1]]


# --- Internationalization --------------------------------------------------

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Dhaka'

USE_I18N = True

USE_TZ = True


# --- Static files and uploads ----------------------------------------------
# On cPanel, point DJANGO_STATIC_ROOT and DJANGO_MEDIA_ROOT inside the domain's
# document root (for example ~/public_html/static and ~/public_html/media) so
# Apache/LiteSpeed serves them directly. WhiteNoise serves STATIC_ROOT as a
# fallback. DJANGO_PRIVATE_MEDIA_ROOT holds files that must only be served by
# permission-checking views (question-paper PDFs); it must stay outside any
# web-served directory.

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = env_path("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles")
MEDIA_URL = "/media/"
MEDIA_ROOT = env_path("DJANGO_MEDIA_ROOT", BASE_DIR / "media")
PRIVATE_MEDIA_ROOT = env_path("DJANGO_PRIVATE_MEDIA_ROOT", BASE_DIR / "private_media")

_private_media = Path(PRIVATE_MEDIA_ROOT).resolve()
for _public_root in (Path(MEDIA_ROOT).resolve(), Path(STATIC_ROOT).resolve()):
    if _private_media == _public_root or _public_root in _private_media.parents:
        raise ImproperlyConfigured(
            "DJANGO_PRIVATE_MEDIA_ROOT must not be inside DJANGO_MEDIA_ROOT or DJANGO_STATIC_ROOT."
        )
if "public_html" in _private_media.parts:
    raise ImproperlyConfigured(
        "DJANGO_PRIVATE_MEDIA_ROOT must be outside public_html; files there can be downloaded directly."
    )

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}

FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755
# Uploads larger than 2.5 MB are buffered to disk; shared hosts often have a
# small /tmp, so allow a directory inside the account instead.
FILE_UPLOAD_TEMP_DIR = env("DJANGO_FILE_UPLOAD_TEMP_DIR") or None


# --- Security --------------------------------------------------------------

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Passenger reports HTTPS to Django directly. Turn the redirect off only if
    # the host loops on redirects; the .htaccess template also forces HTTPS.
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 31_536_000)
    # Subdomain/preload HSTS also binds every other subdomain on the domain
    # (webmail, cpanel, other sites), so they are opt-in.
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
    SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)
    # Trust X-Forwarded-Proto only behind a proxy that always sets it
    # (for example Cloudflare). A direct cPanel host must leave this off.
    if env_bool("DJANGO_SECURE_PROXY_SSL_HEADER", False):
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# --- Logging ---------------------------------------------------------------
# Production logs go to stderr, which Passenger writes to the application's
# log (cPanel: stderr.log in the application root, or the "Passenger log file"
# set in Setup Python App), and optionally to DJANGO_LOG_FILE. Server errors
# are also emailed to DJANGO_ADMINS when it is set.

if not DEBUG:
    LOG_LEVEL = env("DJANGO_LOG_LEVEL", "INFO").upper()
    LOG_FILE = env("DJANGO_LOG_FILE")
    _log_handlers = ["console", "mail_admins"]
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {"require_debug_false": {"()": "django.utils.log.RequireDebugFalse"}},
        "formatters": {
            "verbose": {"format": "{asctime} {levelname} {name} {process:d} {message}", "style": "{"},
        },
        "handlers": {
            "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
            "mail_admins": {
                "class": "django.utils.log.AdminEmailHandler",
                "level": "ERROR",
                "filters": ["require_debug_false"],
            },
        },
        "root": {"handlers": ["console"], "level": "WARNING"},
        "loggers": {
            "django": {"handlers": _log_handlers, "level": LOG_LEVEL, "propagate": False},
        },
    }
    if LOG_FILE:
        Path(LOG_FILE).expanduser().parent.mkdir(parents=True, exist_ok=True)
        LOGGING["handlers"]["file"] = {
            "class": "logging.handlers.WatchedFileHandler",
            "filename": str(Path(LOG_FILE).expanduser()),
            "formatter": "verbose",
        }
        LOGGING["root"]["handlers"].append("file")
        _log_handlers.append("file")

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
