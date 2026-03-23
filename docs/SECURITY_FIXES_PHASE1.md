# Security Fixes — Phase 1

> Generado tras la auditoría de seguridad completa del proyecto.
> Este documento está dirigido al agente que implemente la Fase 2.

---

## Resumen de cambios aplicados

Todos los fixes están en la rama `master`. Se corrigieron **10 bugs** (5 críticos, 3 altos, 2 medios)
encontrados en la auditoría de seguridad antes de poner el proyecto en producción.

---

## FIX 1 — Race condition en `_adjust_reputation`

**Archivo:** `apps/rankings/views.py`

**Problema:** Patrón read-modify-write (`profile.reputation_score += points; profile.save()`)
sin `F()` expression. Bajo carga concurrente dos requests podían leer el mismo valor
y uno de los incrementos se perdía silenciosamente.

**Solución:** Reemplazado por `UserProfile.objects.filter(pk=profile.pk).update(reputation_score=F("reputation_score") + points)`.
La `UPDATE` es atómica a nivel de base de datos.

---

## FIX 2 — `IntegrityError` no capturado en `cast_vote`

**Archivo:** `apps/rankings/views.py`

**Problema:** Dos requests concurrentes que votaban el mismo objeto al mismo tiempo
podían ambos ver `existing_vote = None` y el segundo `Vote.objects.create()` fallaba
con `IntegrityError` (unique_together), resultando en HTTP 500.

**Solución:** Se añadió `select_for_update()` al query de `existing_vote` dentro del
`transaction.atomic()`. Esto adquiere un lock a nivel de fila en PostgreSQL, serializando
el acceso concurrente al mismo (user, content_type, object_id).

---

## FIX 3 — `award_top10_weekly_bonus` no idempotente

**Archivo:** `apps/rankings/tasks.py`

**Problema:** Si Celery reiniciaba o duplicaba la tarea semanal, cada usuario top-10
recibía +100 por cada ejecución. No había guard de idempotencia. Tampoco había
`transaction.atomic()` por usuario.

**Solución:**
- Antes de otorgar el bonus, se verifica en `ReputationLog` si ya existe una entrada
  con `reason="Top 10 semanal — bonus de reputación"` en los últimos 7 días.
- Se envuelve cada usuario en `transaction.atomic()`.
- Se usa `F("reputation_score") + 100` para el UPDATE atómico (igual que FIX 1).

---

## FIX 4 — IDOR en endpoints de audio (CRÍTICO)

**Archivo:** `apps/audio/views.py`

**Problema:** Los endpoints `GET /api/waveform/<model>/<id>/` y
`GET /api/audio/status/<model>/<id>/` no tenían ningún control de acceso.
Cualquier visitante anónimo podía enumerar todos los IDs y obtener las presigned S3 URLs
de archivos privados.

**Solución:** Se añadió el helper `_check_audio_access(request, obj)`:
- Proyectos públicos: accesibles a cualquier visitante (anónimo o autenticado).
- Proyectos privados: sólo accesibles al dueño del proyecto.
- Si el acceso es denegado: retorna 403 JSON (waveform) o 403 HTML (status poll).

**Tests añadidos:** `WaveformAccessControlTest` y `ProcessingStatusPollAccessControlTest`
en `apps/audio/tests/test_views.py`.

---

## FIX 5 — XSS potencial en `_render_player_html`

**Archivo:** `apps/audio/views.py`

**Problema:** La URL de streaming (`audio_src`) se embebía en un string JavaScript
con comillas simples sin escapar: `var url = '...';`. Una URL con `'` o `\` podría
romper el string o inyectar código.

**Solución:** Cambiado a `json.dumps(audio_src)` que serializa la URL como un literal
JavaScript con escaping correcto (comillas dobles + escape de caracteres especiales).

---

## FIX 6 — S3 fallback expone URL directa

**Archivo:** `apps/audio/utils.py`

**Problema:** Si `boto3.generate_presigned_url()` lanzaba una excepción, el fallback
retornaba `file_field.url` — una URL directa de S3 que podía exponer archivos privados
si el bucket tenía ACL pública por error de configuración.

**Solución:** El fallback ahora retorna `None`. Las vistas ya manejan `None` (no muestran
player si no hay URL). No hay exposición de URLs directas en producción.

---

## FIX 7 — `audio_upload_path` con pk=None (CRÍTICO)

**Archivo:** `apps/projects/models.py`

**Problema:** La función `audio_upload_path` usaba `instance.pk` para construir la ruta
del archivo. Django llama a `upload_to` *antes* del primer `save()`, cuando `instance.pk`
es `None`. Todos los archivos nuevos se guardaban en `audio/original/<model>/None/filename`.

**Solución:** Se cambió a usar `uuid.uuid4().hex` como nombre único de archivo.
La ruta es ahora `audio/original/<model>/<uuid>.<ext>`.

**Nota importante para Fase 2:** Los archivos ya existentes en producción permanecen
en la ruta antigua. Si se necesita migrar los archivos existentes, se requiere una
tarea de mantenimiento que renombre los objetos en S3.

---

## FIX 8 — Slug collision en `Project.save()`

**Archivo:** `apps/projects/models.py`

**Problema:** Dos proyectos con el mismo título generaban el mismo slug → `IntegrityError`.
Títulos compuestos sólo por caracteres no-ASCII (chino, árabe, etc.) generaban slug vacío.

**Solución:**
- `slugify("")` o resultado vacío → fallback a `proyecto-<uuid8>`.
- Loop de deduplicación: si el slug ya existe, se añade sufijo `-1`, `-2`, etc.

**Tests añadidos:**
- `test_slug_deduplication` — dos proyectos mismo título → slugs distintos.
- `test_slug_non_ascii_fallback` — título no-ASCII → slug no vacío.

---

## FIX 9 — Race condition TOCTOU en `_increment_upload_count`

**Archivo:** `apps/projects/views.py`

**Problema:** El patrón `try: cache.incr(key) / except ValueError: cache.set(key, 1)`
tenía una race condition TOCTOU: dos requests concurrentes podían ambos fallar en
`incr()` y ambos llamar a `cache.set(key, 1)`, perdiendo un incremento y permitiendo
más uploads que el límite.

**Solución:** Se usa `cache.add(key, 0, timeout=3600)` (atómico: set-if-not-exists)
seguido de `cache.incr(key)`. Mismo patrón aplicado al nuevo `_increment_flag_count`.

---

## FIX 10 — Rate limiting de flags no implementado

**Archivo:** `apps/moderation/views.py`

**Problema:** El docstring de `submit_flag` prometía "Rate limited in middleware/decorator
(20/h)" pero no había ningún rate limiting implementado. Un atacante con 3 cuentas podía
auto-ocultar cualquier contenido en segundos (umbral de auto-hide = 3 flags).

**Solución:** Se añadieron las funciones `_check_flag_rate_limit(user_id)` y
`_increment_flag_count(user_id)` siguiendo exactamente el mismo patrón del rate limiting
de uploads en `projects/views.py`. Límite: 20 flags/hora/usuario. Retorna HTTP 429
si se excede.

---

## Archivos modificados

```
apps/rankings/views.py       — FIX 1, FIX 2
apps/rankings/tasks.py       — FIX 3
apps/audio/views.py          — FIX 4, FIX 5
apps/audio/utils.py          — FIX 6
apps/projects/models.py      — FIX 7, FIX 8
apps/projects/views.py       — FIX 9
apps/moderation/views.py     — FIX 10
```

## Tests actualizados/añadidos

```
apps/audio/tests/test_views.py          — WaveformAccessControlTest (7 nuevos tests)
apps/rankings/tests/test_tasks.py       — test_bonus_not_doubled_on_retry
apps/projects/tests/test_models.py      — test_slug_deduplication, test_slug_non_ascii_fallback
```

---

## Bugs pendientes para Fase 2 (no corregidos en este sprint)

Estos issues fueron identificados en la auditoría pero quedan para la Fase 2:

| Prioridad | Issue | Archivo |
|-----------|-------|---------|
| MEDIO | `FinalMix` no valida que lyrics/beat/vocal_track pertenezcan al mismo proyecto | `apps/projects/models.py` |
| MEDIO | `play_count` en `FinalMix` nunca se incrementa (ninguna vista lo actualiza) | `apps/audio/views.py` |
| BAJO | `moderation_queue` base filter restricts to PENDING+REVIEWING, impidiendo filtrar UPHELD/DISMISSED al staff | `apps/moderation/views.py` |
| BAJO | `except Exception: pass` silencia errores de `transition_to` en `select_contribution` | `apps/projects/views.py:501` |
| BAJO | N+1 en `cast_vote`: `_get_author` accede a FK sin `select_related` en el `get_object_or_404` | `apps/rankings/views.py` |
| BAJO | Credenciales S3 con defaults `minioadmin`/`minioadmin` en `base.py` — deben fallar ruidosamente en prod | `colabmusic/settings/base.py` |

---

## Cómo verificar los fixes

```bash
# Correr todos los tests afectados
python manage.py test \
  apps.rankings.tests \
  apps.audio.tests \
  apps.projects.tests \
  apps.moderation.tests \
  --verbosity=2

# Check de configuración
python manage.py check

# Linting
black apps/ && isort apps/ && flake8 apps/
```
