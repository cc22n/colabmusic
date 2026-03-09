# ColabMusic — Plataforma de Música Colaborativa

## Project Overview

ColabMusic is a collaborative music platform built with Django where users with different musical talents (lyricists, producers, vocalists) come together to create original songs and covers. Each contribution is credited, ranked, and discoverable.

## Tech Stack

- **Backend**: Django 5.x with PostgreSQL
- **Frontend**: HTMX + Tailwind CSS + Alpine.js (no SPA)
- **Audio**: Wavesurfer.js (player), FFmpeg (processing), S3/MinIO (storage)
- **Async**: Celery + Redis (task queue, cache, sessions)
- **Search**: PostgreSQL Full-Text Search via django-watson
- **Auth**: django-allauth (social login + email)

## Project Structure

```
colabmusic/
├── manage.py
├── colabmusic/              # Main config
│   ├── settings/
│   │   ├── base.py          # Shared settings
│   │   ├── development.py   # Local dev overrides
│   │   └── production.py    # Production settings
│   ├── urls.py
│   └── celery.py
├── apps/
│   ├── accounts/            # Auth, profiles, roles
│   ├── projects/            # Projects, lyrics, beats, vocals, mixes
│   ├── audio/               # Upload, processing, streaming
│   ├── rankings/            # Votes, rankings, badges, reputation
│   ├── search/              # Full-text search
│   └── notifications/       # In-app + email notifications
├── templates/
│   ├── base.html
│   ├── components/          # Reusable HTMX partials
│   ├── accounts/
│   ├── projects/
│   └── rankings/
└── static/
    ├── css/
    └── js/
```

## Architecture Decisions

- Users can have MULTIPLE roles simultaneously (ManyToMany, not CharField choices)
- Projects follow a state machine: SEEKING_LYRICS → SEEKING_BEAT → SEEKING_VOCALS → IN_REVIEW → COMPLETE
- Covers skip SEEKING_LYRICS and start at SEEKING_BEAT
- Generic Foreign Keys for the Vote model (one model votes on any content type)
- Audio files are processed async via Celery (convert to MP3 128kbps for streaming, generate waveform JSON)
- Rankings are pre-calculated by Celery beat tasks, cached in Redis
- HTMX for all dynamic interactions — NO JavaScript frameworks

## Code Style

- Python: Black formatter, isort for imports, flake8 for linting
- Templates: 2-space indent, Tailwind utility classes, HTMX attributes
- Models: always define `__str__`, `Meta.ordering`, and `get_absolute_url`
- Views: prefer class-based views (CBV) for CRUD, function-based for HTMX partials
- All text user-facing in Spanish (UI), code/comments in English

## Key Commands

```bash
# Dev server
python manage.py runserver

# Run tests
python manage.py test apps/ --verbosity=2

# Run specific app tests
python manage.py test apps.projects --verbosity=2

# Migrations
python manage.py makemigrations
python manage.py migrate

# Celery worker
celery -A colabmusic worker -l info

# Celery beat (scheduled tasks)
celery -A colabmusic beat -l info

# Tailwind build (watch mode)
npx tailwindcss -i ./static/css/input.css -o ./static/css/output.css --watch

# Type check
python manage.py check --deploy

# Lint
black apps/ && isort apps/ && flake8 apps/
```

## Testing

- Use pytest-django with factory_boy for model factories
- Every model needs a factory in `apps/<app>/tests/factories.py`
- Test files: `test_models.py`, `test_views.py`, `test_forms.py`, `test_tasks.py`
- Use `django.test.TestCase` for DB tests, `SimpleTestCase` for non-DB
- Audio tests use small fixture files in `apps/audio/tests/fixtures/`

## Security Rules — IMPORTANT

- NEVER use `raw()` SQL queries — always use ORM
- NEVER disable CSRF middleware — use `{% csrf_token %}` in forms and `hx-headers` for HTMX
- ALWAYS validate file uploads with python-magic (real MIME check)
- ALWAYS use `login_required` or `LoginRequiredMixin` on protected views
- ALWAYS check object ownership before allowing edit/delete
- Presigned URLs for S3 with 1-hour expiration
- Rate limit uploads: max 10/hour per user

## Git Workflow

- Branch naming: `feature/<description>`, `fix/<description>`, `refactor/<description>`
- Commit messages: conventional commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`)
- Always create a new branch per feature — never commit directly to main
- Run tests before committing

## Common Patterns

### HTMX Partial Response
Views that serve HTMX partials should check `request.headers.get('HX-Request')` and return only the fragment, not the full page.

### Audio Upload Flow
1. User submits form → Django validates → saves temp file
2. Celery task: validate with FFprobe → extract metadata → convert to MP3 → generate waveform → upload to S3
3. Update model with processing_status = READY

### Voting
Use `contenttypes` framework with Generic FK. One Vote model handles FinalMix, Lyrics, Beat, and VocalTrack.

@docs/TECHNICAL_DESIGN.md
