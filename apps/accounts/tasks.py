from celery import shared_task


@shared_task
def award_badge_if_eligible(user_id: int) -> None:
    """Check and award badges to a user based on their activity."""
    pass


@shared_task
def recalculate_reputation(user_id: int) -> None:
    """Recalculate a user's reputation score from scratch."""
    pass
