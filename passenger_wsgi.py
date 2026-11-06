"""Phusion Passenger entry point for cPanel "Setup Python App".

In cPanel set:
    Application startup file: passenger_wsgi.py
    Application Entry point:  application

Configuration is read from the .env file in this directory (see
deploy/cpanel/README.md). Restart the app after changing it, either with the
Restart button in cPanel or by touching tmp/restart.txt.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "MathKangaroo.settings")
# The public site never runs in DEBUG unless DJANGO_DEBUG explicitly says so.
os.environ.setdefault("DJANGO_DEBUG_DEFAULT", "false")

from MathKangaroo.wsgi import application  # noqa: E402,F401
