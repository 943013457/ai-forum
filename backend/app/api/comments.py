from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Comment, Post
from app.schemas import CommentOut, PaginatedResponse

router = APIRouter()


@router.get("/post/{post_id}", response_model=PaginatedResponse)
async def list_comments_for_post(
    post_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    total = (await db.execute(
        select(func.count()).where(Comment.post_id == post_id, Comment.parent_comment_id.is_(None))
    )).scalar() or 0

    stmt = (
        select(Comment)
        .options(selectinload(Comment.author), selectinload(Comment.replies).selectinload(Comment.author))
        .where(Comment.post_id == post_id, Comment.parent_comment_id.is_(None))
        .order_by(Comment.created_at)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    comments = result.scalars().all()

    from app.schemas import UserBrief

    def build(c):
        out = CommentOut.model_validate(c)
        if c.author:
            out.author = UserBrief.model_validate(c.author)
        out.replies = [build(r) for r in (c.replies or [])]
        return out

    items = [build(c) for c in comments]

    return PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )
