"""
Development settings for ColabMusic.
"""

from .base import *  # noqa: F401, F403

DEBUG = True

# Allow all hosts in development
ALLOWED_HOSTS = ["*"]

# Use SQLite for quick local dev if DATABASE_URL not set
# Already handled via env.db() fallback in base.py

# Django Debug Toolbar (optional, add to requirements if needed)
# INSTALLED_APPS += ["debug_toolbar"]

# Disable password hashing for speed in tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Email to console in development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Use local filesystem storage instead of S3 in development
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
