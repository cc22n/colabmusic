# 🎵 ColabMusic

Plataforma de música colaborativa donde letristas, productores y vocalistas se unen para crear canciones originales y covers. Cada contribución es acreditada, votada y visible en rankings públicos.

---

## Características principales

| Feature | Detalle |
|---|---|
| **Proyectos colaborativos** | Originales (letra → beat → voces) y Covers (beat → voces) con máquina de estados |
| **Audio pipeline** | Subida de archivos, conversión a MP3 128 kbps, generación de waveform JSON via FFmpeg + Celery |
| **Reproductor** | Wavesurfer.js integrado con streaming desde S3/MinIO |
| **Votación** | Upvote / downvote sobre letras, beats, voces y mixes con GenericFK |
| **Rankings** | Global, por rol, por género y covers — pre-calculados en caché con Celery beat |
| **Reputación** | Sistema de puntos + insignias + bonus Top-10 semanal |
| **Búsqueda** | Full-text search sobre proyectos, letras y perfiles con django-watson |
| **Notificaciones** | In-app con badge HTMX (polling 30s) + email para eventos importantes |
| **Moderación** | Sistema de reportes con umbral de auto-ocultamiento y cola de revisión |
| **Auth social** | django-allauth con roles de usuario múltiples (Letrista / Productor / Vocalista) |

---

## Tech Stack

```
Backend     Django 5.x · PostgreSQL (SQLite en dev)
Frontend    HTMX · Tailwind CSS · Alpine.js   ← sin SPA
Audio       Wavesurfer.js · FFmpeg · S3/MinIO
Async       Celery + Redis (tareas, caché, sesiones)
Search      django-watson (PostgreSQL Full-Text Search)
Auth        django-allauth (email + social login)
```

---

## Estructura del proyecto

```
colabmusic/
├── manage.py
├── colabmusic/                 # Configuración principal
│   ├── settings/
│   │   ├── base.py             # Ajustes compartidos
│   │   ├── development.py      # Overrides locales
│   │   └── production.py       # Producción
│   ├── urls.py
│   └── celery.py
├── apps/
│   ├── accounts/               # Auth, perfiles, roles, géneros, insignias
│   ├── projects/               # Proyectos, letras, beats, voces, mixes
│   ├── audio/                  # Upload, procesamiento, streaming
│   ├── rankings/               # Votos, rankings, reputación
│   ├── search/                 # Full-text search
│   └── notifications/          # Notificaciones in-app + email
├── templates/
│   ├── base.html
│   ├── components/             # Navbar, search box, partials HTMX
│   ├── accounts/
│   ├── projects/
│   ├── rankings/
│   ├── audio/
│   ├── moderation/
│   └── notifications/
└── static/
    ├── css/
    └── js/
```

---

## Configuración local

### 1. Pre-requisitos

- Python 3.11+
- Redis (para Celery)
- FFmpeg en PATH (para procesamiento de audio)
- MinIO o cuenta S3 (opcional en dev — usar almacenamiento local)

### 2. Clonar e instalar dependencias

```bash
git clone https://github.com/tu-usuario/colabmusic.git
cd colabmusic
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Variables de entorno

Copia el archivo de ejemplo y edítalo:

```bash
cp .env.example .env
```

Variables requeridas:

```env
SECRET_KEY=django-secret-key-muy-larga
DEBUG=True
DATABASE_URL=postgres://user:pass@localhost:5432/colabmusic
REDIS_URL=redis://localhost:6379/0
S3_BUCKET_NAME=colab-music
S3_ENDPOINT_URL=http://localhost:9000
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
ALLOWED_HOSTS=localhost,127.0.0.1
```

> **Tip:** En desarrollo se puede omitir `DATABASE_URL` para usar SQLite automáticamente.

### 4. Base de datos y superusuario

```bash
python manage.py migrate
python manage.py createsuperuser
```

La migración `accounts.0002_seed_roles` crea los tres roles base (Letrista, Productor, Vocalista) automáticamente.

### 5. Servidor de desarrollo

```bash
# Django
python manage.py runserver

# Celery worker (en otra terminal)
celery -A colabmusic worker -l info

# Celery beat — tareas programadas (en otra terminal)
celery -A colabmusic beat -l info

# Tailwind en modo watch (en otra terminal)
npx tailwindcss -i ./static/css/input.css -o ./static/css/output.css --watch
```

---

## Comandos útiles

```bash
# Tests
python manage.py test apps.accounts.tests apps.projects.tests \
  apps.audio.tests apps.rankings.tests apps.search.tests \
  apps.notifications.tests.test_tasks apps.notifications.tests.test_views \
  apps.notifications.tests.test_models --verbosity=2

# Migraciones
python manage.py makemigrations
python manage.py migrate

# Linting y formato
black apps/ && isort apps/ && flake8 apps/

# Check de deploy
python manage.py check --deploy
```

---

## Flujo de estados de un proyecto

```
ORIGINAL:   SEEKING_LYRICS → SEEKING_BEAT → SEEKING_VOCALS → IN_REVIEW → COMPLETE
COVER:                        SEEKING_BEAT → SEEKING_VOCALS → IN_REVIEW → COMPLETE
Cualquier estado              → ARCHIVED  (solo el creador)
```

---

## Pipeline de audio

```
1. Usuario sube archivo  →  Django valida MIME con python-magic
2. Celery task:
     a. FFprobe extrae metadatos (duración, bitrate, formato)
     b. FFmpeg convierte a MP3 128 kbps
     c. Genera waveform JSON (para Wavesurfer.js)
     d. Sube ambos archivos a S3/MinIO
3. Modelo actualiza processing_status = READY
4. HTMX polling (/api/audio/status/<id>/) actualiza el reproductor
```

---

## Sistema de reputación

| Acción | Puntos |
|--------|--------|
| Upvote recibido | +10 |
| Downvote recibido | −2 |
| Canción completada | +50 |
| Top 10 semanal (bonus) | +100 |
| Primera contribución aceptada | +25 |

Los rankings se pre-calculan cada hora (semanal) y cada día (mensual) via Celery beat y se almacenan en `RankingCache` como JSON.

---

## Tareas programadas (Celery beat)

| Tarea | Frecuencia | Descripción |
|-------|-----------|-------------|
| `calculate_rankings` (weekly) | Cada hora | Rankings globales, por rol, género y covers |
| `calculate_rankings` (monthly) | Cada día | Ídem para período mensual |
| `award_top10_weekly_bonus` | Cada semana | +100 pts a usuarios en Top 10 semanal |
| `cleanup_old_notifications` | Cada día | Elimina notificaciones leídas de +90 días |

---

## URLs principales

```
/                              Inicio (trending, recientes)
/projects/                     Explorar proyectos
/projects/new/                 Crear proyecto
/projects/<slug>/              Detalle del proyecto
/covers/                       Explorar covers
/rankings/                     Rankings globales
/rankings/trending/            Trending ahora
/rankings/by-role/<role>/      Rankings por rol
/rankings/by-genre/<genre>/    Rankings por género
/rankings/covers/              Top covers
/search/                       Búsqueda full-text
/notifications/                Bandeja de notificaciones
/accounts/profile/<username>/  Perfil público
/accounts/settings/            Editar perfil
```

---

## Seguridad

- Sin consultas SQL raw — siempre ORM
- CSRF habilitado + `hx-headers` en todas las peticiones HTMX
- Validación MIME real con `python-magic` en uploads de audio
- `login_required` / `LoginRequiredMixin` en todas las vistas protegidas
- Verificación de propiedad antes de editar / eliminar
- Presigned URLs en S3 con expiración de 1 hora
- Rate limit de uploads: máx. 10/hora por usuario

---

## Tests

```
173 tests — 0 fallos
```

Organización por app:

```
apps/<app>/tests/
├── factories.py      # factory_boy
├── test_models.py
├── test_views.py
├── test_forms.py     # donde aplica
└── test_tasks.py     # audio, rankings, notifications
```

---

## Historial de desarrollo

| Fase | Feature |
|------|---------|
| 1 | Scaffold inicial — todos los modelos y apps |
| 2 | Projects CRUD y vistas de exploración |
| 3 | Perfiles de usuario, roles y géneros |
| 4 | Templates de autenticación con roles en signup |
| 5 | Sistema de moderación y reportes de contenido |
| 6 | Pipeline de audio — upload, FFmpeg, Wavesurfer.js |
| 7 | Búsqueda full-text con django-watson |
| 8 | Sistema de votación con GenericFK |
| 9 | Rankings pre-calculados + Celery beat |
| 10 | Notificaciones in-app + email + bell HTMX |

---

## Licencia

MIT © ColabMusic
