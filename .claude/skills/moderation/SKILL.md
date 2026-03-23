---
name: moderation
description: "Content moderation and flagging system for ColabMusic. Use this skill when working on reporting, flagging, content moderation, auto-flag thresholds, moderation queues, or admin review workflows. Also use when the user mentions flags, reports, moderation, copyright claims, or content removal."
---

# Moderation System — ColabMusic

## Overview

Users can flag songs/audio (FinalMix, Beat, VocalTrack) and lyrics (Lyrics) for copyright infringement, plagiarism, or offensive content. The system auto-hides content when it reaches a configurable report threshold, then admins review and take action.

## Models

### Flag (User Report)

Uses Generic FK pattern (same as Vote model).

```python
class FlagReason(models.TextChoices):
    COPYRIGHT = "copyright", "Infracción de derechos de autor"
    PLAGIARISM = "plagiarism", "Plagio de contenido"
    OFFENSIVE = "offensive", "Contenido ofensivo o inapropiado"
    SPAM = "spam", "Spam o contenido no relacionado"
    OTHER = "other", "Otro"

class FlagStatus(models.TextChoices):
    PENDING = "pending", "Pendiente de revisión"
    REVIEWING = "reviewing", "En revisión"
    UPHELD = "upheld", "Reporte confirmado"
    DISMISSED = "dismissed", "Reporte descartado"

class Flag(models.Model):
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="flags_submitted")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    
    reason = models.CharField(max_length=20, choices=FlagReason.choices)
    description = models.TextField(
        max_length=500,
        blank=True,
        help_text="Descripción opcional del problema"
    )
    status = models.CharField(
        max_length=20,
        choices=FlagStatus.choices,
        default=FlagStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["reporter", "content_type", "object_id"],
                name="unique_flag_per_user_per_content",
            )
        ]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Flag #{self.pk} — {self.get_reason_display()} on {self.content_type.model} #{self.object_id}"
```

### ModerationAction (Admin Decision)

```python
class ActionType(models.TextChoices):
    REMOVE_CONTENT = "remove", "Contenido removido"
    HIDE_CONTENT = "hide", "Contenido oculto temporalmente"
    DISMISS = "dismiss", "Reporte descartado"
    WARN_USER = "warn", "Advertencia al usuario"
    BAN_USER = "ban", "Usuario suspendido"

class ModerationAction(models.Model):
    flag = models.ForeignKey(Flag, on_delete=models.CASCADE, related_name="actions")
    moderator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="moderation_actions")
    action_type = models.CharField(max_length=20, choices=ActionType.choices)
    notes = models.TextField(blank=True, help_text="Notas internas del moderador")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_type_display()} by {self.moderator} on Flag #{self.flag_id}"
```

### ContentModerationMixin (Abstract — add to flaggable models)

```python
class ContentModerationMixin(models.Model):
    """Add to FinalMix, Beat, VocalTrack, Lyrics."""
    is_hidden = models.BooleanField(
        default=False,
        help_text="Oculto por moderación automática o manual"
    )
    hidden_at = models.DateTimeField(null=True, blank=True)
    hidden_reason = models.CharField(max_length=100, blank=True)
    flag_count = models.PositiveIntegerField(
        default=0,
        help_text="Contador denormalizado de flags activos"
    )

    class Meta:
        abstract = True

    def hide(self, reason="Auto-flag threshold reached"):
        self.is_hidden = True
        self.hidden_at = timezone.now()
        self.hidden_reason = reason
        self.save(update_fields=["is_hidden", "hidden_at", "hidden_reason"])

    def unhide(self):
        self.is_hidden = False
        self.hidden_at = None
        self.hidden_reason = ""
        self.save(update_fields=["is_hidden", "hidden_at", "hidden_reason"])
```

## Auto-Flag Configuration

```python
# settings/base.py
MODERATION_AUTO_HIDE_THRESHOLD = 3  # Flags to auto-hide content
MODERATION_NOTIFY_THRESHOLD = 1     # Flags to notify admins
```

## Celery Task: check_flag_threshold

```python
@shared_task
def check_flag_threshold(flag_id):
    """
    Triggered after each new Flag is created.
    
    1. Count active (PENDING + REVIEWING) flags for the content
    2. Update flag_count on the content object
    3. If count >= MODERATION_AUTO_HIDE_THRESHOLD:
       - Set is_hidden = True on the content
       - Create notification for all admin/moderator users
       - Log the auto-hide action
    4. If count >= MODERATION_NOTIFY_THRESHOLD:
       - Create notification for admins
    """
    flag = Flag.objects.select_related("content_type").get(id=flag_id)
    content_model = flag.content_type.model_class()
    content_obj = content_model.objects.get(id=flag.object_id)
    
    active_flags = Flag.objects.filter(
        content_type=flag.content_type,
        object_id=flag.object_id,
        status__in=[FlagStatus.PENDING, FlagStatus.REVIEWING],
    ).count()
    
    # Update denormalized counter
    content_obj.flag_count = active_flags
    content_obj.save(update_fields=["flag_count"])
    
    threshold = settings.MODERATION_AUTO_HIDE_THRESHOLD
    if active_flags >= threshold and not content_obj.is_hidden:
        content_obj.hide(reason=f"Auto-hidden: {active_flags} flags received")
        # Notify admins
        notify_moderators.delay(
            flag.content_type_id, flag.object_id, active_flags
        )
```

## Views

### Flag Submission (HTMX)

```python
@login_required
@ratelimit(key="user", rate="20/h", method="POST", block=True)
def submit_flag(request, content_type_str, object_id):
    """
    POST endpoint for flagging content.
    Returns HTMX partial with confirmation or error.
    
    URL: /moderation/flag/<content_type>/<object_id>/
    """
    # 1. Resolve content_type from string (finalmix, beat, vocaltrack, lyrics)
    # 2. Validate the content object exists
    # 3. Check user hasn't already flagged this content (unique constraint)
    # 4. Create Flag from form data (reason + description)
    # 5. Dispatch check_flag_threshold.delay(flag.id)
    # 6. Return HTMX partial with success message
```

### Moderation Queue (Admin-only)

```python
@login_required
@user_passes_test(lambda u: u.is_staff)
def moderation_queue(request):
    """
    Dashboard showing pending flags grouped by content.
    
    URL: /moderation/queue/
    """
    # Group flags by content_type + object_id
    # Show: content preview, flag count, reasons, reporters
    # Actions: Review, Dismiss All, Hide Content, Remove Content

@login_required
@user_passes_test(lambda u: u.is_staff)
def resolve_flag(request, flag_id):
    """
    POST endpoint to take moderation action on a flag.
    
    URL: /moderation/resolve/<flag_id>/
    """
    # 1. Create ModerationAction
    # 2. Update Flag.status (upheld or dismissed)
    # 3. If upheld: hide/remove content, notify content owner
    # 4. If dismissed: unhide if was auto-hidden, notify reporter
    # 5. Return updated queue partial
```

## HTMX Components

### Flag Button (add to audio player and lyrics display)

```html
<!-- templates/components/flag_button.html -->
<div id="flag-{{ content_type }}-{{ object_id }}">
  {% if user.is_authenticated %}
  <button
    hx-get="{% url 'moderation:flag-form' content_type object_id %}"
    hx-target="#flag-modal"
    hx-swap="innerHTML"
    class="text-gray-400 hover:text-red-500 transition text-sm flex items-center gap-1"
    title="Reportar contenido"
  >
    ⚑ Reportar
  </button>
  {% endif %}
</div>
```

### Flag Form Modal

```html
<!-- templates/moderation/flag_form.html -->
<div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
     x-data="{ open: true }" x-show="open" @click.self="open = false">
  <div class="bg-white rounded-xl p-6 max-w-md w-full mx-4 shadow-2xl">
    <h3 class="text-lg font-bold text-gray-900 mb-4">Reportar contenido</h3>
    <form hx-post="{% url 'moderation:submit-flag' content_type object_id %}"
          hx-target="#flag-{{ content_type }}-{{ object_id }}"
          hx-swap="outerHTML"
          @htmx:after-request="open = false">
      
      <div class="space-y-3 mb-4">
        {% for value, label in flag_reasons %}
        <label class="flex items-center gap-3 p-2 rounded hover:bg-gray-50 cursor-pointer">
          <input type="radio" name="reason" value="{{ value }}" required
                 class="text-red-500 focus:ring-red-500">
          <span class="text-sm text-gray-700">{{ label }}</span>
        </label>
        {% endfor %}
      </div>
      
      <textarea name="description" rows="3" maxlength="500"
                placeholder="Describe el problema (opcional)..."
                class="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-red-500 mb-4">
      </textarea>
      
      <div class="flex gap-3 justify-end">
        <button type="button" @click="open = false"
                class="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">
          Cancelar
        </button>
        <button type="submit"
                class="px-4 py-2 bg-red-500 text-white text-sm rounded-lg hover:bg-red-600 transition">
          Enviar reporte
        </button>
      </div>
    </form>
  </div>
</div>
```

## URL Patterns

```python
# apps/moderation/urls.py
app_name = "moderation"

urlpatterns = [
    # User-facing
    path("flag/<str:content_type>/<int:object_id>/", views.flag_form, name="flag-form"),
    path("flag/<str:content_type>/<int:object_id>/submit/", views.submit_flag, name="submit-flag"),
    
    # Admin moderation queue
    path("queue/", views.moderation_queue, name="queue"),
    path("resolve/<int:flag_id>/", views.resolve_flag, name="resolve-flag"),
]
```

## QuerySet Filter — Hide Flagged Content

Add a custom manager to flaggable models:

```python
class VisibleManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_hidden=False)

class FinalMix(ContentModerationMixin, AudioMixin, models.Model):
    # ... fields ...
    
    objects = models.Manager()       # Default: all objects
    visible = VisibleManager()       # Filtered: only non-hidden
    
    # In views, ALWAYS use:
    # FinalMix.visible.all() instead of FinalMix.objects.all()
```

## Integration Checklist

When implementing, remember to:
1. Add `ContentModerationMixin` to: FinalMix, Beat, VocalTrack, Lyrics
2. Run `makemigrations` (adds is_hidden, hidden_at, hidden_reason, flag_count)
3. Replace `Model.objects.all()` with `Model.visible.all()` in ALL public-facing views
4. Add the flag button component to: audio player, lyrics display, project detail
5. Add `moderation` to INSTALLED_APPS
6. Include moderation URLs in main urls.py
7. Add Celery task to beat schedule (or just use post-save dispatch)
8. Create admin views for the moderation queue
9. Add tests for: flag creation, duplicate prevention, auto-hide threshold, admin resolution

## Security

- Rate limit flag submissions: 20/hour per user (prevent flag abuse)
- Unique constraint: one flag per user per content (no spam flagging)
- Only authenticated users can flag
- Only staff users can access moderation queue
- Log all moderation actions for audit trail
- Notify content owner when their content is hidden/removed
- Notify reporter when their flag is resolved
