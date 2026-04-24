from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import (
    User, Post, Comment, UserFollow, UserAchievement, UserBan,
    Like, Debate, DebateVote,
)
from app.schemas import (
    UserOut, UserProfile, UserBrief, PostOut, AchievementOut,
    BanOut, PaginatedResponse, DebateOut,
)

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("credits", regex="^(credits|newest|posts)$"),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User).where(User.is_system == False)

    if sort == "credits":
        stmt = stmt.order_by(desc(User.credits))
    elif sort == "newest":
        stmt = stmt.order_by(desc(User.created_at))
    elif sort == "posts":
        stmt = stmt.outerjoin(Post, Post.author_id == User.id).group_by(User.id).order_by(
            desc(func.count(Post.id))
        )

    count_stmt = select(func.count()).select_from(
        select(User).where(User.is_system == False).subquery()
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    users = result.scalars().all()

    return PaginatedResponse(
        items=[UserBrief.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/{user_id}", response_model=UserProfile)
async def get_user_profile(user_id: int, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(
        select(User).where(User.id == user_id)
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    profile = UserProfile.model_validate(user)

    profile.follower_count = (await db.execute(
        select(func.count()).where(UserFollow.following_id == user_id)
    )).scalar() or 0

    profile.following_count = (await db.execute(
        select(func.count()).where(UserFollow.follower_id == user_id)
    )).scalar() or 0

    profile.post_count = (await db.execute(
        select(func.count()).where(Post.author_id == user_id)
    )).scalar() or 0

    profile.comment_count = (await db.execute(
        select(func.count()).where(Comment.author_id == user_id)
    )).scalar() or 0

    achievements = (await db.execute(
        select(UserAchievement).where(UserAchievement.user_id == user_id)
    )).scalars().all()
    profile.achievements = [AchievementOut.model_validate(a) for a in achievements]

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    ban = (await db.execute(
        select(UserBan).where(
            UserBan.user_id == user_id,
            (UserBan.banned_until.is_(None)) | (UserBan.banned_until > now),
        ).order_by(desc(UserBan.created_at)).limit(1)
    )).scalar_one_or_none()
    if ban:
        profile.ban_status = BanOut.model_validate(ban)

    return profile


@router.get("/{user_id}/posts", response_model=PaginatedResponse)
async def get_user_posts(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Post)
        .options(selectinload(Post.tags), selectinload(Post.author))
        .where(Post.author_id == user_id)
        .order_by(desc(Post.created_at))
    )
    total = (await db.execute(
        select(func.count()).where(Post.author_id == user_id)
    )).scalar() or 0

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    posts = result.scalars().all()

    items = []
    for p in posts:
        data = {c.key: getattr(p, c.key) for c in p.__table__.columns}
        data["tags"] = [t.name for t in p.tags] if p.tags else []
        if p.author:
            from app.schemas import UserBrief
            data["author"] = UserBrief.model_validate(p.author)
        items.append(PostOut(**data))

    return PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/{user_id}/followers", response_model=PaginatedResponse)
async def get_user_followers(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    total = (await db.execute(
        select(func.count()).where(UserFollow.following_id == user_id)
    )).scalar() or 0

    stmt = (
        select(User)
        .join(UserFollow, UserFollow.follower_id == User.id)
        .where(UserFollow.following_id == user_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    users = result.scalars().all()

    return PaginatedResponse(
        items=[UserBrief.model_validate(u) for u in users],
        total=total, page=page, page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/{user_id}/debates", response_model=list)
async def get_user_debates(user_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Debate).where(
        (Debate.user_a_id == user_id) | (Debate.user_b_id == user_id)
    ).order_by(desc(Debate.created_at)).limit(20)
    result = await db.execute(stmt)
    return [DebateOut.model_validate(d) for d in result.scalars().all()]
