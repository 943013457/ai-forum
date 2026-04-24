from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Post, User, Comment, Tag, PostTag, Like, Poll, PollVote
from app.schemas import PostOut, PostDetail, PaginatedResponse, PollOut, PollVoteCreate

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def list_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("latest", regex="^(latest|hot|featured)$"),
    tag: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Post).options(selectinload(Post.author), selectinload(Post.tags))

    if tag:
        stmt = stmt.join(PostTag).join(Tag).where(Tag.name == tag)

    if sort == "latest":
        stmt = stmt.order_by(desc(Post.is_pinned), desc(Post.created_at))
    elif sort == "hot":
        stmt = stmt.order_by(
            desc(Post.is_pinned),
            desc(Post.like_count * 2 + Post.comment_count * 5 + Post.view_count * 0.1),
        )
    elif sort == "featured":
        stmt = stmt.where(Post.is_featured == True).order_by(desc(Post.created_at))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    posts = result.scalars().all()

    items = []
    for p in posts:
        data = {
            c.key: getattr(p, c.key)
            for c in p.__table__.columns
        }
        data["tags"] = [t.name for t in p.tags] if p.tags else []
        if p.author:
            from app.schemas import UserBrief
            data["author"] = UserBrief.model_validate(p.author)
        items.append(PostOut(**data))

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/{post_id}", response_model=PostDetail)
async def get_post(post_id: int, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Post)
        .options(
            selectinload(Post.author),
            selectinload(Post.tags),
            selectinload(Post.comments).selectinload(Comment.author),
            selectinload(Post.comments).selectinload(Comment.replies),
            selectinload(Post.poll).selectinload(Poll.votes),
        )
        .where(Post.id == post_id)
    )
    result = await db.execute(stmt)
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    post.view_count += 1
    await db.commit()

    data = {c.key: getattr(post, c.key) for c in post.__table__.columns}
    data["tags"] = [t.name for t in post.tags] if post.tags else []
    if post.author:
        from app.schemas import UserBrief
        data["author"] = UserBrief.model_validate(post.author)
    out = PostDetail(**data)

    top_comments = [c for c in post.comments if c.parent_comment_id is None]
    from app.schemas import CommentOut, UserBrief as UB

    def build_comment(c):
        co = CommentOut.model_validate(c)
        if c.author:
            co.author = UB.model_validate(c.author)
        co.replies = [build_comment(r) for r in (c.replies or [])]
        return co

    out.comments = [build_comment(c) for c in top_comments]

    if post.poll:
        vote_counts = {}
        for v in post.poll.votes:
            vote_counts[v.option_index] = vote_counts.get(v.option_index, 0) + 1
        out.poll = PollOut(
            id=post.poll.id,
            post_id=post.poll.post_id,
            options=post.poll.options,
            votes=vote_counts,
            total_votes=len(post.poll.votes),
        )

    return out


@router.post("/{post_id}/vote")
async def vote_poll(post_id: int, body: PollVoteCreate, db: AsyncSession = Depends(get_db)):
    poll = (await db.execute(
        select(Poll).where(Poll.post_id == post_id)
    )).scalar_one_or_none()
    if not poll:
        raise HTTPException(status_code=404, detail="投票不存在")

    if body.option_index < 0 or body.option_index >= len(poll.options):
        raise HTTPException(status_code=400, detail="无效选项")

    vote = PollVote(poll_id=poll.id, user_id=0, option_index=body.option_index)
    db.add(vote)
    await db.commit()
    return {"ok": True}
