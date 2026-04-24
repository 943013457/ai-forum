from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.database import get_db
from app.models import Tag, PostTag, Post
from app.schemas import TagOut

router = APIRouter()


@router.get("", response_model=list[TagOut])
async def list_tags(
    sort: str = Query("count", regex="^(count|name)$"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(
            Tag.id,
            Tag.name,
            func.count(PostTag.post_id).label("post_count"),
        )
        .outerjoin(PostTag, PostTag.tag_id == Tag.id)
        .group_by(Tag.id, Tag.name)
    )

    if sort == "count":
        stmt = stmt.order_by(desc("post_count"))
    else:
        stmt = stmt.order_by(Tag.name)

    stmt = stmt.limit(limit)
    result = await db.execute(stmt)

    return [
        TagOut(id=row.id, name=row.name, post_count=row.post_count)
        for row in result.all()
    ]


@router.get("/trending", response_model=list[TagOut])
async def trending_tags(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    stmt = (
        select(
            Tag.id,
            Tag.name,
            func.count(PostTag.post_id).label("post_count"),
        )
        .join(PostTag, PostTag.tag_id == Tag.id)
        .join(Post, Post.id == PostTag.post_id)
        .where(Post.created_at >= cutoff)
        .group_by(Tag.id, Tag.name)
        .order_by(desc("post_count"))
        .limit(limit)
    )
    result = await db.execute(stmt)

    return [
        TagOut(id=row.id, name=row.name, post_count=row.post_count)
        for row in result.all()
    ]
