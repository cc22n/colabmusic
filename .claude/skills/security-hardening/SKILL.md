---
name: security-hardening
description: "Security best practices and OWASP protections for ColabMusic. Use this skill when implementing authentication, authorization, file uploads, input validation, rate limiting, or any security-related feature. Also use when reviewing code for vulnerabilities or when the user mentions security, auth, permissions, CSRF, or XSS."
---

# Security Hardening — ColabMusic

## Authentication (django-allauth)

```python
# settings/base.py
INSTALLED_APPS = [
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    # Social providers as needed
]

ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_LOGIN_ATTEMPTS_LIMIT = 5
ACCOUNT_LOGIN_ATTEMPTS_TIMEOUT = 300  # 5 min lockout
LOGIN_REDIRECT_URL = "/"
```

## Authorization Patterns

```python
# ALWAYS check ownership before edit/delete
from django.core.exceptions import PermissionDenied

class ProjectUpdateView(LoginRequiredMixin, UpdateView):
    model = Project

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.created_by != self.request.user:
            raise PermissionDenied("No tienes permiso para editar este proyecto.")
        return obj
```

For role-based access, use a custom decorator:

```python
from functools import wraps

def role_required(*role_names):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not request.user.profile.roles.filter(name__in=role_names).exists():
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

# Usage
@role_required("PRODUCER")
def submit_beat(request, project_id):
    ...
```

## File Upload Security

```python
import magic

ALLOWED_AUDIO_MIMES = {
    "audio/mpeg", "audio/wav", "audio/x-wav", "audio/flac",
    "audio/ogg", "audio/aac", "audio/mp4",
}
MAX_AUDIO_SIZE = 50 * 1024 * 1024  # 50MB

def validate_audio_file(uploaded_file):
    """Validate audio file MIME type and size."""
    # Check size
    if uploaded_file.size > MAX_AUDIO_SIZE:
        raise ValidationError("El archivo excede el límite de 50MB.")

    # Check REAL MIME type (not just extension!)
    mime = magic.from_buffer(uploaded_file.read(2048), mime=True)
    uploaded_file.seek(0)  # Reset pointer!

    if mime not in ALLOWED_AUDIO_MIMES:
        raise ValidationError(f"Tipo de archivo no permitido: {mime}")

    return True
```

## CSRF Protection

- Django CSRF middleware is ALWAYS enabled — never add to CSRF_EXEMPT
- HTMX: set `hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'` on `<body>`
- AJAX calls: include token in headers from cookie
- NEVER use `@csrf_exempt` on any view

## Rate Limiting

```python
from django_ratelimit.decorators import ratelimit

@ratelimit(key="user", rate="10/h", method="POST", block=True)
def upload_audio(request, project_id):
    ...

@ratelimit(key="user", rate="60/h", method="POST", block=True)
def vote(request, content_type, object_id):
    ...

@ratelimit(key="ip", rate="5/m", method="POST", block=True)
def login_view(request):
    ...
```

## Security Headers (Middleware)

```python
# settings/production.py
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"

# CSP via django-csp
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "https://unpkg.com")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")  # Tailwind needs this
CSP_MEDIA_SRC = ("'self'", "https://*.s3.amazonaws.com")
CSP_IMG_SRC = ("'self'", "data:", "https://*.s3.amazonaws.com")
```

## Input Validation

- ALWAYS use Django Forms or ModelForms for user input
- NEVER trust `request.POST` or `request.GET` directly without validation
- Use `bleach` to sanitize any user-generated HTML (bios, descriptions)
- Validate slugs, IDs, and status values against allowed sets

## SQL Injection Prevention

- ALWAYS use Django ORM — never `connection.cursor()` with string formatting
- If raw SQL is absolutely necessary: `Model.objects.raw("SELECT ... WHERE id = %s", [user_id])`
- NEVER use f-strings or `.format()` in queries

## Dependencies

- `django-allauth` — authentication
- `django-ratelimit` — rate limiting
- `django-csp` — Content Security Policy headers
- `python-magic` — MIME type validation
- `bleach` — HTML sanitization
