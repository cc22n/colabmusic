"""
Celery tasks for the rankings app.

calculate_rankings   — pre-calculate RankingCache for all types and a given period.
award_top10_weekly_bonus — award +100 reputation to users in top-10 weekly ranking.
"""

from datetime import timedelta

from celery import shared_task
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Count, F
from django.utils import timezone


def _since(period: str):
    """Return the earliest datetime for *period*, or None for all_time."""
    now = timezone.now()
    if period == "weekly":
        return now - timedelta(days=7)
    if period == "monthly":
        return now - timedelta(days=30)
    return None


def _upvotes_qs(since):
    """Return a Vote queryset filtered to upvotes (and period if given)."""
    from apps.rankings.models import Vote

    qs = Vote.objects.filter(vote_type=Vote.VoteType.UPVOTE)
    if since:
        qs = qs.filter(created_at__gte=since)
    return qs


def _project_entries_by_vote(projects, vote_counts):
    """
    Rank *projects* by upvotes on their FinalMix.
    Returns a JSON-serialisable list of dicts, top-20 max.
    """
    scored = []
    for p in projects:
        mix = getattr(p, "final_mix", None)
        score = vote_counts.get(mix.pk, 0) if mix else 0
        scored.append((score, p))
    scored.sort(key=lambda x: -x[0])
    return [
        {
            "rank": i + 1,
            "project_id": p.pk,
            "title": p.title,
            "slug": p.slug,
            "upvotes": score,
            "author": p.created_by.username,
            "project_type": p.project_type,
        }
        for i, (score, p) in enumerate(scored[:20])
    ]


@shared_task
def calculate_rankings(period: str = "weekly") -> None:
    """
    Pre-calculate and cache rankings for a given period.
    Calculates: global, by_role, by_genre, covers.
    """
    from apps.accounts.models import Genre, Role, UserProfile
    from apps.projects.models import FinalMix, Project
    from apps.rankings.models import RankingCache

    since = _since(period)
    finalmix_ct = ContentType.objects.get_for_model(FinalMix)

    # ── 1. Global: top 50 users by reputation_score ──────────────────────────
    profiles = list(
        UserProfile.objects.select_related("user")
        .prefetch_related("roles")
        .order_by("-reputation_score")[:50]
    )
    global_entries = [
        {
            "rank": i + 1,
            "user_id": p.user.pk,
            "username": p.user.username,
            "display_name": str(p),
            "reputation_score": p.reputation_score,
            "roles": [r.display_name for r in p.roles.all()],
        }
        for i, p in enumerate(profiles)
    ]
    RankingCache.objects.update_or_create(
        ranking_type="global",
        period=period,
        genre=None,
        role=None,
        defaults={"entries": global_entries},
    )

    # ── 2. By role: top 20 users per role ────────────────────────────────────
    for role in Role.objects.all():
        role_profiles = list(
            UserProfile.objects.filter(roles=role)
            .select_related("user")
            .order_by("-reputation_score")[:20]
        )
        role_entries = [
            {
                "rank": i + 1,
                "user_id": p.user.pk,
                "username": p.user.username,
                "display_name": str(p),
                "reputation_score": p.reputation_score,
            }
            for i, p in enumerate(role_profiles)
        ]
        RankingCache.objects.update_or_create(
            ranking_type="by_role",
            period=period,
            genre=None,
            role=role,
            defaults={"entries": role_entries},
        )

    # ── 3 & 4. Build vote-count map for FinalMix objects (reused below) ───────
    vote_counts = {
        row["object_id"]: row["count"]
        for row in _upvotes_qs(since)
        .filter(content_type=finalmix_ct)
        .values("object_id")
        .annotate(count=Count("id"))
    }

    # ── 3. By genre: top 20 public projects per genre ────────────────────────
    for genre in Genre.objects.all():
        genre_projects = list(
            Project.objects.filter(is_public=True, genre=genre).select_related(
                "created_by", "final_mix"
            )
        )
        RankingCache.objects.update_or_create(
            ranking_type="by_genre",
            period=period,
            genre=genre,
            role=None,
            defaults={"entries": _project_entries_by_vote(genre_projects, vote_counts)},
        )

    # ── 4. Covers: top 20 public cover projects ───────────────────────────────
    cover_projects = list(
        Project.objects.filter(is_public=True, project_type="cover").select_related(
            "created_by", "final_mix"
        )
    )
    RankingCache.objects.update_or_create(
        ranking_type="covers",
        period=period,
        genre=None,
        role=None,
        defaults={"entries": _project_entries_by_vote(cover_projects, vote_counts)},
    )


@shared_task
def award_top10_weekly_bonus() -> None:
    """
    Award +100 reputation to users in the top-10 weekly global ranking.

    Idempotent: checks ReputationLog for an existing bonus entry in the last 7 days
    before awarding, so retries or duplicate runs never grant the bonus twice.
    Uses F() expression + transaction.atomic() for each user to be race-condition safe.
    """
    from apps.accounts.models import UserProfile
    from apps.rankings.models import RankingCache, ReputationLog

    try:
        ranking_cache = RankingCache.objects.get(
            ranking_type="global",
            period="weekly",
            genre=None,
            role=None,
        )
    except RankingCache.DoesNotExist:
        return

    # Idempotency window: same 7-day rolling window used by _since("weekly")
    week_start = timezone.now() - timedelta(days=7)
    bonus_reason = "Top 10 semanal — bonus de reputación"

    for entry in ranking_cache.entries[:10]:
        try:
            profile = UserProfile.objects.select_related("user").get(
                user_id=entry["user_id"]
            )
        except UserProfile.DoesNotExist:
            continue

        with transaction.atomic():
            # Guard: skip if this user already received the bonus this week
            already_awarded = ReputationLog.objects.filter(
                user=profile.user,
                reason=bonus_reason,
                created_at__gte=week_start,
            ).exists()
            if already_awarded:
                continue

            # Atomic UPDATE — avoids read-modify-write race condition
            UserProfile.objects.filter(pk=profile.pk).update(
                reputation_score=F("reputation_score") + 100
            )
            ReputationLog.objects.create(
                user=profile.user,
                points=100,
                reason=bonus_reason,
            )
