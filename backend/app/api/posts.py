from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Post, User, Comment, Tag, PostTag, Like, CommentLike, Poll, PollVote
from app.schemas import PostOut, PostDetail, CommentOut, PaginatedResponse, PollOut, PollVoteCreate, UserBrief

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
        data["author"] = UserBrief.model_validate(post.author)
    out = PostDetail(**data)
    out.comments = []  # 评论通过独立分页接口加载

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


@router.get("/{post_id}/comments", response_model=PaginatedResponse)
async def get_post_comments(
    post_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("mixed", regex="^(mixed|likes|latest)$"),
    db: AsyncSession = Depends(get_db),
):
    """获取帖子的顶级评论（分页），子评论嵌套返回。
    sort: mixed=最热+最新混合, likes=按点赞, latest=按时间"""
    # 只查顶级评论
    base = select(Comment).where(
        Comment.post_id == post_id,
        Comment.parent_comment_id.is_(None),
    )
    total = (await db.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar() or 0

    if sort == "likes":
        stmt = base.order_by(desc(Comment.like_count), desc(Comment.created_at))
    elif sort == "latest":
        stmt = base.order_by(desc(Comment.created_at))
    else:
        # mixed: 前 3 条按点赞最多，其余按最新
        hot_stmt = base.order_by(desc(Comment.like_count), desc(Comment.created_at)).limit(3)
        hot_result = await db.execute(hot_stmt.options(
            selectinload(Comment.author),
            selectinload(Comment.replies).selectinload(Comment.author),
            selectinload(Comment.replies).selectinload(Comment.replies).selectinload(Comment.author),
        ))
        hot_comments = list(hot_result.scalars().all())
        hot_ids = {c.id for c in hot_comments}

        rest_stmt = (
            base.where(Comment.id.notin_(hot_ids) if hot_ids else True)
            .order_by(desc(Comment.created_at))
            .offset(max(0, (page - 1) * page_size - len(hot_ids)) if page == 1 else (page - 1) * page_size)
            .limit(page_size - len(hot_ids) if page == 1 else page_size)
        ).options(
            selectinload(Comment.author),
            selectinload(Comment.replies).selectinload(Comment.author),
            selectinload(Comment.replies).selectinload(Comment.replies).selectinload(Comment.author),
        )
        rest_result = await db.execute(rest_stmt)
        rest_comments = list(rest_result.scalars().all())

        comments = (hot_comments + rest_comments) if page == 1 else rest_comments
        items = [_build_comment(c) for c in comments]
        return PaginatedResponse(
            items=items, total=total, page=page,
            page_size=page_size, pages=(total + page_size - 1) // page_size,
        )

    stmt = stmt.offset((page - 1) * page_size).limit(page_size).options(
        selectinload(Comment.author),
        selectinload(Comment.replies).selectinload(Comment.author),
        selectinload(Comment.replies).selectinload(Comment.replies).selectinload(Comment.author),
    )
    result = await db.execute(stmt)
    comments = list(result.scalars().all())
    items = [_build_comment(c) for c in comments]

    return PaginatedResponse(
        items=items, total=total, page=page,
        page_size=page_size, pages=(total + page_size - 1) // page_size,
    )


def _comment_to_dict(c) -> dict:
    """将 ORM Comment 转为 dict，避免触发 lazy-load"""
    return {
        "id": c.id,
        "post_id": c.post_id,
        "author_id": c.author_id,
        "content": c.content,
        "parent_comment_id": c.parent_comment_id,
        "like_count": c.like_count,
        "created_at": c.created_at,
        "author": UserBrief.model_validate(c.author) if c.author else None,
        "replies": [],
    }


def _build_comment(c, depth=0, max_depth=3) -> dict:
    """递归构建评论树（最多 max_depth 层）"""
    data = _comment_to_dict(c)
    if depth < max_depth - 1:
        replies = getattr(c, "replies", None) or []
        data["replies"] = [_build_comment(r, depth + 1, max_depth) for r in replies]
    return data


@router.post("/{post_id}/comments/{comment_id}/like")
async def toggle_comment_like(
    post_id: int, comment_id: int,
    db: AsyncSession = Depends(get_db),
):
    comment = (await db.execute(
        select(Comment).where(Comment.id == comment_id, Comment.post_id == post_id)
    )).scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")

    # 使用 user_id=0 表示匿名点赞（与帖子点赞逻辑一致）
    existing = (await db.execute(
        select(CommentLike).where(
            CommentLike.comment_id == comment_id,
            CommentLike.user_id == 0,
        )
    )).scalar_one_or_none()

    if existing:
        await db.delete(existing)
        comment.like_count = max(0, comment.like_count - 1)
    else:
        db.add(CommentLike(comment_id=comment_id, user_id=0))
        comment.like_count += 1

    await db.commit()
    return {"ok": True, "like_count": comment.like_count}


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
