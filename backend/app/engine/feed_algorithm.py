import random
import math
import logging
from datetime import datetime, timezone
from typing import List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import User, Post, UserFollow

logger = logging.getLogger(__name__)


class FeedAlgorithm:
    async def get_personalized_feed(
        self, db: AsyncSession, user: User, limit: int = None
    ) -> List[Post]:
        limit = limit or settings.FEED_TOP_N
        candidates = await self._get_candidate_posts(db, user, limit * 10)

        if not candidates:
            return []

        following_ids = await self._get_following_ids(db, user.id)
        scored = []
        for post in candidates:
            score = self._score_post(user, post, following_ids)
            scored.append((post, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        entropy_count = max(1, int(limit * settings.ENTROPY_RATIO))
        main_count = limit - entropy_count

        result = [p for p, _ in scored[:main_count]]

        remaining = [p for p, _ in scored[main_count:]]
        if remaining:
            random_picks = random.sample(remaining, min(entropy_count, len(remaining)))
            result.extend(random_picks)

        random.shuffle(result)
        return result[:limit]

    async def _get_candidate_posts(
        self, db: AsyncSession, user: User, limit: int
    ) -> List[Post]:
        if user.interest_embedding is not None:
            stmt = (
                select(Post)
                .options(selectinload(Post.author))
                .where(Post.content_embedding.isnot(None))
                .order_by(
                    Post.content_embedding.cosine_distance(user.interest_embedding)
                )
                .limit(limit)
            )
        else:
            stmt = (
                select(Post)
                .options(selectinload(Post.author))
                .order_by(Post.created_at.desc())
                .limit(limit)
            )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def _get_following_ids(self, db: AsyncSession, user_id: int) -> set:
        stmt = select(UserFollow.following_id).where(UserFollow.follower_id == user_id)
        result = await db.execute(stmt)
        return set(result.scalars().all())

    def _score_post(self, user: User, post: Post, following_ids: set) -> float:
        match_score = 0.5

        hot_score = self._calculate_hot_score(post)
        max_hot = 1000.0
        normalized_hot = min(hot_score / max_hot, 1.0)

        author_credit_score = 0.0
        if hasattr(post, "author") and post.author:
            author_credit_score = min(post.author.credits / 1000.0, 1.0)

        final_score = (
            settings.FEED_MATCH_WEIGHT * match_score
            + settings.FEED_HOT_WEIGHT * normalized_hot
            + settings.FEED_CREDIT_WEIGHT * author_credit_score
        )

        if post.author_id in following_ids:
            final_score *= settings.FOLLOW_FEED_BOOST

        if post.is_featured:
            final_score *= 1.3
        if post.is_pinned:
            final_score *= 2.0

        return final_score

    def _calculate_hot_score(self, post: Post) -> float:
        raw_heat = (
            post.like_count * settings.HOT_LIKE_WEIGHT
            + post.comment_count * settings.HOT_COMMENT_WEIGHT
            + post.view_count * settings.HOT_VIEW_WEIGHT
        )
        now = datetime.now(timezone.utc)
        age_hours = max((now - post.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600.0, 0.1)
        decayed = raw_heat / math.pow(age_hours + 1, settings.HOT_DECAY_POWER)
        return decayed


feed_algorithm = FeedAlgorithm()
