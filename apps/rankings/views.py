"""
Views for the rankings app.
cast_vote: HTMX endpoint to up/downvote any supported content type.
RankingsView: top users by reputation.
TrendingView: recent public projects.
RankingByGenreView: projects filtered by genre (stub).
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import F
from django.http import HttpResponseBadRequest, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, render
from django.views.generic import ListView

from apps.accounts.models import Genre, UserProfile
from apps.projects.models import Project

from .models import ReputationLog, Vote

User = get_user_model()

# Supported votable model lookup: str → (app_label, model_name, author_field)
# author_field is the FK field name on the model that points to the user to credit.
# None means no reputation change (e.g. FinalMix has no single author).
VOTABLE_MODELS = {
    "beat": ("projects", "beat", "producer"),
    "lyrics": ("projects", "lyrics", "author"),
    "vocal": ("projects", "vocaltrack", "vocalist"),
    "mix": ("projects", "finalmix", None),
}

# Reputation deltas
UPVOTE_POINTS = 10
DOWNVOTE_POINTS = -2


def _get_author(obj, author_field):
    """Return the User credited as author of *obj*, or None."""
    if author_field is None:
        return None
    return getattr(obj, author_field, None)


@login_required
def cast_vote(request, content_type_str, object_id):
    """
    POST /rankings/vote/<content_type_str>/<object_id>/

    Toggle or switch vote. Returns the updated vote_buttons partial.
    GET → 405. Unknown content_type_str → 400.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    config = VOTABLE_MODELS.get(content_type_str)
    if config is None:
        return HttpResponseBadRequest("Tipo de contenido no válido.")

    app_label, model_name, author_field = config

    ct = get_object_or_404(ContentType, app_label=app_label, model=model_name)
    obj = get_object_or_404(ct.model_class(), pk=object_id)
    author = _get_author(obj, author_field)

    vote_type_raw = request.POST.get("vote_type", Vote.VoteType.UPVOTE)
    if vote_type_raw not in (Vote.VoteType.UPVOTE, Vote.VoteType.DOWNVOTE):
        return HttpResponseBadRequest("Tipo de voto no válido.")

    with transaction.atomic():
        # select_for_update() serializa acceso concurrente al mismo (user, content, object)
        # evitando IntegrityError por unique_together bajo carga simultánea.
        existing_vote = Vote.objects.select_for_update().filter(
            user=request.user, content_type=ct, object_id=object_id
        ).first()

        if existing_vote:
            if existing_vote.vote_type == vote_type_raw:
                # Toggle off: remove vote and revert reputation
                _adjust_reputation(
                    author,
                    request.user,
                    points=-_points_for(vote_type_raw),
                    reason=f"Toggle off {vote_type_raw} on {model_name} #{object_id}",
                )
                existing_vote.delete()
            else:
                # Switch vote: apply delta
                old_points = _points_for(existing_vote.vote_type)
                new_points = _points_for(vote_type_raw)
                _adjust_reputation(
                    author,
                    request.user,
                    points=new_points - old_points,
                    reason=f"Changed vote to {vote_type_raw} on {model_name} #{object_id}",
                )
                existing_vote.vote_type = vote_type_raw
                existing_vote.save(update_fields=["vote_type"])
        else:
            # New vote
            Vote.objects.create(
                user=request.user,
                content_type=ct,
                object_id=object_id,
                vote_type=vote_type_raw,
            )
            _adjust_reputation(
                author,
                request.user,
                points=_points_for(vote_type_raw),
                reason=f"Received {vote_type_raw} on {model_name} #{object_id}",
            )
            # Notify the author of the upvote (not for self-votes or downvotes)
            if (
                author
                and author != request.user
                and vote_type_raw == Vote.VoteType.UPVOTE
            ):
                from apps.notifications.tasks import send_notification

                send_notification.delay(
                    recipient_id=author.pk,
                    notification_type="vote_received",
                    title="Recibiste un voto positivo",
                    message=(
                        f"{request.user.username} votó positivamente "
                        f"tu {model_name}."
                    ),
                    sender_id=request.user.pk,
                )

    # Re-render the vote_buttons partial with fresh counts
    qs = Vote.objects.filter(content_type=ct, object_id=object_id)
    upvotes = qs.filter(vote_type=Vote.VoteType.UPVOTE).count()
    downvotes = qs.filter(vote_type=Vote.VoteType.DOWNVOTE).count()
    current_vote = qs.filter(user=request.user).first()
    user_vote = current_vote.vote_type if current_vote else None

    return render(
        request,
        "components/vote_buttons.html",
        {
            "content_type_str": content_type_str,
            "object_id": object_id,
            "upvotes": upvotes,
            "downvotes": downvotes,
            "user_vote": user_vote,
            "upvote_value": Vote.VoteType.UPVOTE,
            "downvote_value": Vote.VoteType.DOWNVOTE,
        },
    )


def _points_for(vote_type):
    return UPVOTE_POINTS if vote_type == Vote.VoteType.UPVOTE else DOWNVOTE_POINTS


def _adjust_reputation(author, voter, points, reason):
    """
    Award *points* to *author*'s reputation.
    A voter cannot gain/lose reputation from their own votes.
    Uses F() expression for an atomic UPDATE — avoids read-modify-write race condition
    under concurrent votes on the same content.
    Creates a ReputationLog entry for audit.
    """
    if author is None or author == voter:
        return
    profile = getattr(author, "profile", None)
    if profile is None:
        return
    # Atomic UPDATE — safe under concurrent requests hitting the same author
    from apps.accounts.models import UserProfile
    UserProfile.objects.filter(pk=profile.pk).update(
        reputation_score=F("reputation_score") + points
    )
    ReputationLog.objects.create(user=author, points=points, reason=reason)


class RankingsView(ListView):
    """Top users ranked by reputation score."""

    model = UserProfile
    template_name = "rankings/rankings.html"
    context_object_name = "profiles"
    paginate_by = 20

    def get_queryset(self):
        return (
            UserProfile.objects.select_related("user")
            .prefetch_related("roles")
            .order_by("-reputation_score")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["is_trending"] = False
        ctx["page_title"] = "Rankings Globales"
        return ctx


class TrendingView(ListView):
    """Recently active public projects."""

    model = Project
    template_name = "rankings/rankings.html"
    context_object_name = "projects"
    paginate_by = 20

    def get_queryset(self):
        return (
            Project.objects.filter(is_public=True)
            .select_related("created_by", "genre")
            .order_by("-updated_at")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["is_trending"] = True
        ctx["page_title"] = "Trending"
        return ctx


class RankingByGenreView(ListView):
    """Public projects filtered by genre slug."""

    model = Project
    template_name = "rankings/rankings.html"
    context_object_name = "projects"
    paginate_by = 20

    def get_queryset(self):
        self.genre = get_object_or_404(Genre, slug=self.kwargs["genre"])
        return (
            Project.objects.filter(is_public=True, genre=self.genre)
            .select_related("created_by", "genre")
            .order_by("-updated_at")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["is_trending"] = True
        ctx["genre"] = self.genre
        ctx["page_title"] = f"Proyectos de {self.genre.name}"
        return ctx


class RankingByRoleView(ListView):
    """Top users filtered by musical role."""

    model = UserProfile
    template_name = "rankings/rankings.html"
    context_object_name = "profiles"
    paginate_by = 20

    def get_queryset(self):
        from apps.accounts.models import Role

        self.role = get_object_or_404(Role, name=self.kwargs["role"])
        return (
            UserProfile.objects.filter(roles=self.role)
            .select_related("user")
            .prefetch_related("roles")
            .order_by("-reputation_score")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["is_trending"] = False
        ctx["active_role"] = self.role
        ctx["page_title"] = f"Top {self.role.display_name}s"
        return ctx


class CoverRankingsView(ListView):
    """Top public cover projects ordered by recency."""

    model = Project
    template_name = "rankings/rankings.html"
    context_object_name = "projects"
    paginate_by = 20

    def get_queryset(self):
        return (
            Project.objects.filter(is_public=True, project_type="cover")
            .select_related("created_by", "genre")
            .order_by("-updated_at")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["is_trending"] = True
        ctx["is_covers"] = True
        ctx["page_title"] = "Covers"
        return ctx
