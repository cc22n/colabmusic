"""
Template tags for the voting system.
Usage:
    {% load vote_tags %}
    {% vote_buttons "beat" beat %}
    {% vote_buttons "lyrics" lyrics %}
"""

from django import template
from django.contrib.contenttypes.models import ContentType

from apps.rankings.models import Vote

register = template.Library()

# Map of string name → app_label.model_name for supported votable types
VOTABLE_MODELS = {
    "beat": ("projects", "beat"),
    "lyrics": ("projects", "lyrics"),
    "vocal": ("projects", "vocaltrack"),
    "mix": ("projects", "finalmix"),
}


@register.inclusion_tag("components/vote_buttons.html", takes_context=True)
def vote_buttons(context, content_type_str, obj):
    """
    Render upvote/downvote buttons for *obj*.

    Args:
        content_type_str: one of "beat", "lyrics", "vocal", "mix"
        obj: the Django model instance being voted on
    """
    request = context.get("request")
    user = request.user if request else None

    upvotes = 0
    downvotes = 0
    user_vote = None  # "upvote" | "downvote" | None

    app_label, model_name = VOTABLE_MODELS.get(content_type_str, (None, None))
    if app_label and model_name:
        try:
            ct = ContentType.objects.get(app_label=app_label, model=model_name)
            qs = Vote.objects.filter(content_type=ct, object_id=obj.pk)
            upvotes = qs.filter(vote_type=Vote.VoteType.UPVOTE).count()
            downvotes = qs.filter(vote_type=Vote.VoteType.DOWNVOTE).count()
            if user and user.is_authenticated:
                existing = qs.filter(user=user).first()
                if existing:
                    user_vote = existing.vote_type
        except ContentType.DoesNotExist:
            pass

    return {
        "request": request,
        "content_type_str": content_type_str,
        "object_id": obj.pk,
        "upvotes": upvotes,
        "downvotes": downvotes,
        "user_vote": user_vote,
        "upvote_value": Vote.VoteType.UPVOTE,
        "downvote_value": Vote.VoteType.DOWNVOTE,
    }
