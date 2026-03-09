from celery import shared_task


@shared_task
def calculate_rankings(period: str = "weekly") -> None:
    """
    Pre-calculate and cache rankings for a given period.
    Runs on Celery beat schedule.
    Calculates: global, by_role, by_genre, covers rankings.
    """
    pass


@shared_task
def update_reputation_on_vote(vote_id: int) -> None:
    """
    Update the author's reputation score after a vote is cast.
    Points: upvote +10, downvote -2.
    """
    pass


@shared_task
def award_top10_weekly_bonus() -> None:
    """Award +100 reputation to users in top 10 weekly rankings."""
    pass
