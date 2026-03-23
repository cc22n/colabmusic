"""
Views for the moderation app.
submit_flag: HTMX POST — creates a Flag, dispatches Celery task.
flag_form:   HTMX GET  — returns the modal form partial.
moderation_queue: staff-only dashboard of pending flags.
resolve_flag: staff POST — creates ModerationAction, updates Flag status.
"""

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, render

from .forms import FlagForm, ResolveForm
from .models import ActionType, Flag, FlagReason, FlagStatus, ModerationAction
from .tasks import check_flag_threshold

# Maps URL slug → (app_label, model_name)
FLAGGABLE_MODELS = {
    "beat": ("projects", "beat"),
    "lyrics": ("projects", "lyrics"),
    "vocal": ("projects", "vocaltrack"),
    "mix": ("projects", "finalmix"),
}


FLAG_RATE_LIMIT = 20  # max flags per hour per user


def _is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def _staff_check(user):
    return user.is_active and user.is_staff


def _check_flag_rate_limit(user_id: int) -> bool:
    """Return True if the user is within the flag rate limit (20/hour)."""
    return cache.get(f"flag_rate:{user_id}", 0) < FLAG_RATE_LIMIT


def _increment_flag_count(user_id: int) -> None:
    """
    Increment the per-user flag counter (expires in 1 hour).
    Uses cache.add() for atomic set-if-not-exists to avoid TOCTOU race condition.
    """
    key = f"flag_rate:{user_id}"
    if not cache.add(key, 0, timeout=3600):
        cache.incr(key)
    else:
        cache.incr(key)


# ── Flag form (HTMX GET) ──────────────────────────────────────────────────────


@login_required
def flag_form(request, content_type_str, object_id):
    """Return the flag modal HTML fragment (HTMX GET only)."""
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    config = FLAGGABLE_MODELS.get(content_type_str)
    if config is None:
        return HttpResponseBadRequest("Tipo de contenido no soportado.")

    app_label, model_name = config
    ct = get_object_or_404(ContentType, app_label=app_label, model=model_name)
    # Verify the object actually exists
    get_object_or_404(ct.model_class(), pk=object_id)

    # Check if user already flagged this
    already_flagged = Flag.objects.filter(
        reporter=request.user,
        content_type=ct,
        object_id=object_id,
    ).exists()

    return render(
        request,
        "moderation/flag_form.html",
        {
            "form": FlagForm(),
            "content_type_str": content_type_str,
            "object_id": object_id,
            "flag_reasons": FlagReason.choices,
            "already_flagged": already_flagged,
        },
    )


# ── Submit flag (HTMX POST) ───────────────────────────────────────────────────


@login_required
def submit_flag(request, content_type_str, object_id):
    """
    POST /moderation/flag/<content_type>/<object_id>/submit/
    Rate limited: 20 flags per hour per user. Returns HTMX partial.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    # Rate limit: prevent spam-flagging to abuse auto-hide threshold
    if not _check_flag_rate_limit(request.user.id):
        if _is_htmx(request):
            return HttpResponse(
                '<p class="text-red-400 text-sm">'
                "Demasiados reportes. Límite: 20 por hora."
                "</p>",
                status=429,
            )
        return HttpResponse("Demasiados reportes. Límite: 20 por hora.", status=429)

    config = FLAGGABLE_MODELS.get(content_type_str)
    if config is None:
        return HttpResponseBadRequest("Tipo de contenido no soportado.")

    app_label, model_name = config
    ct = get_object_or_404(ContentType, app_label=app_label, model=model_name)
    get_object_or_404(ct.model_class(), pk=object_id)

    form = FlagForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "moderation/flag_form.html",
            {
                "form": form,
                "content_type_str": content_type_str,
                "object_id": object_id,
                "flag_reasons": FlagReason.choices,
                "already_flagged": False,
            },
            status=422,
        )

    try:
        with transaction.atomic():
            flag = Flag.objects.create(
                reporter=request.user,
                content_type=ct,
                object_id=object_id,
                reason=form.cleaned_data["reason"],
                description=form.cleaned_data.get("description", ""),
            )
    except IntegrityError:
        # unique_flag_per_user_per_content constraint — already flagged
        return render(
            request,
            "moderation/flag_confirm.html",
            {"already_flagged": True, "content_type_str": content_type_str, "object_id": object_id},
        )

    # Increment rate limit counter after successful flag creation
    _increment_flag_count(request.user.id)

    # Dispatch async threshold check
    check_flag_threshold.delay(flag.id)

    return render(
        request,
        "moderation/flag_confirm.html",
        {"already_flagged": False, "content_type_str": content_type_str, "object_id": object_id},
    )


# ── Moderation queue (staff only) ─────────────────────────────────────────────


@login_required
@user_passes_test(_staff_check)
def moderation_queue(request):
    """Staff dashboard: pending + reviewing flags grouped by content."""
    status_filter = request.GET.get("status", FlagStatus.PENDING)
    flags = (
        Flag.objects.filter(status__in=[FlagStatus.PENDING, FlagStatus.REVIEWING])
        .select_related("reporter", "content_type")
        .order_by("-created_at")
    )
    if status_filter and status_filter in FlagStatus.values:
        flags = flags.filter(status=status_filter)

    return render(
        request,
        "moderation/queue.html",
        {
            "flags": flags,
            "status_filter": status_filter,
            "status_choices": FlagStatus.choices,
            "resolve_form": ResolveForm(),
        },
    )


# ── Resolve flag (staff POST) ─────────────────────────────────────────────────


@login_required
@user_passes_test(_staff_check)
def resolve_flag(request, flag_id):
    """
    POST /moderation/resolve/<flag_id>/
    Staff takes a moderation action (uphold or dismiss) and optionally
    hides/unhides the content.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    flag = get_object_or_404(Flag, id=flag_id)
    form = ResolveForm(request.POST)

    if not form.is_valid():
        if _is_htmx(request):
            return HttpResponse(
                '<p class="text-red-400 text-sm">Formulario inválido.</p>', status=422
            )
        return HttpResponseBadRequest("Formulario inválido.")

    action_type = form.cleaned_data["action_type"]
    notes = form.cleaned_data.get("notes", "")

    # Create audit record
    ModerationAction.objects.create(
        flag=flag,
        moderator=request.user,
        action_type=action_type,
        notes=notes,
    )

    # Update flag status
    if action_type in (ActionType.REMOVE_CONTENT, ActionType.HIDE_CONTENT, ActionType.WARN_USER, ActionType.BAN_USER):
        flag.status = FlagStatus.UPHELD
    else:  # DISMISS
        flag.status = FlagStatus.DISMISSED

    flag.save(update_fields=["status", "updated_at"])

    # Act on the content object
    ct = flag.content_type
    content_model = ct.model_class()
    try:
        content_obj = content_model.objects.get(id=flag.object_id)
        if action_type in (ActionType.HIDE_CONTENT, ActionType.REMOVE_CONTENT):
            if hasattr(content_obj, "hide"):
                content_obj.hide(reason=f"Moderación: {flag.get_reason_display()}")
        elif action_type == ActionType.DISMISS:
            # Unhide if it was auto-hidden and there are no other upheld flags
            other_upheld = Flag.objects.filter(
                content_type=ct,
                object_id=flag.object_id,
                status=FlagStatus.UPHELD,
            ).exclude(id=flag.id).exists()
            if not other_upheld and hasattr(content_obj, "unhide"):
                content_obj.unhide()
    except content_model.DoesNotExist:
        pass

    if _is_htmx(request):
        return HttpResponse(
            f'<span class="text-green-400 text-xs font-medium">'
            f'✓ {flag.get_status_display()}</span>'
        )

    from django.shortcuts import redirect
    return redirect("moderation:queue")
