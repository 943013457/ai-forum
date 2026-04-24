from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, update

from app.database import get_db
from app.config import settings
from app.models import (
    User, Post, Comment, Announcement, AnnouncementReward,
    UserBan, CreditLog, EngineLog, DailyTopic, Debate, RumorChain,
)
from app.schemas import (
    AnnouncementCreate, AnnouncementOut, BanCreate, BanOut,
    EngineStatus, EngineLogOut, DailyTopicOut, CreditLogOut,
    PaginatedResponse,
)

router = APIRouter()

DURATION_MAP = {
    "24h": timedelta(hours=24),
    "3d": timedelta(days=3),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "permanent": None,
}


# ==================== 引擎控制 ====================
@router.get("/engine/status", response_model=EngineStatus)
async def engine_status(db: AsyncSession = Depends(get_db)):
    from app.engine.world_engine import world_engine
    from app.services.llm_service import llm_service

    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    total_posts = (await db.execute(select(func.count(Post.id)))).scalar() or 0
    total_comments = (await db.execute(select(func.count(Comment.id)))).scalar() or 0

    return EngineStatus(
        running=world_engine.running,
        tick_number=world_engine.tick_number,
        total_users=total_users,
        total_posts=total_posts,
        total_comments=total_comments,
        llm_calls_this_hour=llm_service.call_count,
    )


@router.post("/engine/stop")
async def stop_engine():
    from app.engine.world_engine import world_engine
    world_engine.stop()
    return {"ok": True, "message": "引擎已停止"}


@router.post("/engine/generate-users")
async def generate_users(count: int = Query(50, ge=1, le=500), db: AsyncSession = Depends(get_db)):
    from app.engine.persona_generator import persona_generator
    users = await persona_generator.generate_batch(db, count)
    return {"ok": True, "generated": len(users)}


@router.get("/engine/logs", response_model=list[EngineLogOut])
async def engine_logs(limit: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_db)):
    stmt = select(EngineLog).order_by(desc(EngineLog.timestamp)).limit(limit)
    result = await db.execute(stmt)
    return [EngineLogOut.model_validate(l) for l in result.scalars().all()]


# ==================== 公告管理 ====================
@router.get("/announcements", response_model=list[AnnouncementOut])
async def list_announcements(db: AsyncSession = Depends(get_db)):
    stmt = select(Announcement).order_by(desc(Announcement.created_at))
    result = await db.execute(stmt)
    return [AnnouncementOut.model_validate(a) for a in result.scalars().all()]


@router.post("/announcements", response_model=AnnouncementOut)
async def create_announcement(body: AnnouncementCreate, db: AsyncSession = Depends(get_db)):
    ann = Announcement(**body.model_dump())
    db.add(ann)
    await db.commit()
    await db.refresh(ann)
    return AnnouncementOut.model_validate(ann)


@router.delete("/announcements/{ann_id}")
async def delete_announcement(ann_id: int, db: AsyncSession = Depends(get_db)):
    ann = (await db.execute(select(Announcement).where(Announcement.id == ann_id))).scalar_one_or_none()
    if not ann:
        raise HTTPException(status_code=404, detail="公告不存在")
    await db.delete(ann)
    await db.commit()
    return {"ok": True}


# ==================== 精选管理 ====================
@router.post("/posts/{post_id}/feature")
async def toggle_featured(post_id: int, db: AsyncSession = Depends(get_db)):
    post = (await db.execute(select(Post).where(Post.id == post_id))).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    post.is_featured = not post.is_featured

    if post.is_featured and settings.FEATURED_POST_REWARD > 0:
        author = (await db.execute(select(User).where(User.id == post.author_id))).scalar_one_or_none()
        if author:
            author.credits += settings.FEATURED_POST_REWARD
            db.add(CreditLog(
                user_id=author.id,
                amount=settings.FEATURED_POST_REWARD,
                reason="文章被精选",
                related_post_id=post.id,
            ))

    await db.commit()
    return {"ok": True, "is_featured": post.is_featured}


@router.post("/posts/{post_id}/pin")
async def toggle_pinned(post_id: int, db: AsyncSession = Depends(get_db)):
    post = (await db.execute(select(Post).where(Post.id == post_id))).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    post.is_pinned = not post.is_pinned
    await db.commit()
    return {"ok": True, "is_pinned": post.is_pinned}


@router.post("/posts/{post_id}/mark-rumor")
async def mark_rumor(post_id: int, db: AsyncSession = Depends(get_db)):
    post = (await db.execute(select(Post).where(Post.id == post_id))).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    post.is_rumor = True
    await db.commit()
    return {"ok": True}


@router.post("/posts/{post_id}/mark-delete")
async def mark_for_delete(post_id: int, db: AsyncSession = Depends(get_db)):
    """标记帖子为待删除，24小时后自动删除"""
    post = (await db.execute(select(Post).where(Post.id == post_id))).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    if post.marked_for_delete_at:
        return {"ok": True, "marked_for_delete_at": post.marked_for_delete_at.isoformat()}
    post.marked_for_delete_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True, "marked_for_delete_at": post.marked_for_delete_at.isoformat()}


@router.post("/posts/{post_id}/unmark-delete")
async def unmark_for_delete(post_id: int, db: AsyncSession = Depends(get_db)):
    """取消删除标记"""
    post = (await db.execute(select(Post).where(Post.id == post_id))).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    post.marked_for_delete_at = None
    await db.commit()
    return {"ok": True}


@router.put("/daily-topics/{topic_id}")
async def update_daily_topic(topic_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    """更新每日话题标题和描述"""
    topic = (await db.execute(select(DailyTopic).where(DailyTopic.id == topic_id))).scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="话题不存在")
    if "title" in body:
        topic.title = body["title"]
    if "description" in body:
        topic.description = body["description"]
    await db.commit()
    return {"ok": True, "title": topic.title, "description": topic.description}


# ==================== 禁言管理 ====================
@router.get("/bans", response_model=list[BanOut])
async def list_bans(db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    stmt = select(UserBan).where(
        (UserBan.banned_until.is_(None)) | (UserBan.banned_until > now)
    ).order_by(desc(UserBan.created_at))
    result = await db.execute(stmt)
    return [BanOut.model_validate(b) for b in result.scalars().all()]


@router.post("/bans", response_model=BanOut)
async def create_ban(body: BanCreate, db: AsyncSession = Depends(get_db)):
    duration = DURATION_MAP.get(body.duration)
    banned_until = None
    if body.duration and body.duration != "permanent":
        banned_until = datetime.now(timezone.utc) + duration

    ban = UserBan(
        user_id=body.user_id,
        reason=body.reason,
        banned_until=banned_until,
        created_by=settings.ADMIN_USERNAME,
    )
    db.add(ban)
    await db.commit()
    await db.refresh(ban)
    return BanOut.model_validate(ban)


@router.delete("/bans/{ban_id}")
async def remove_ban(ban_id: int, db: AsyncSession = Depends(get_db)):
    ban = (await db.execute(select(UserBan).where(UserBan.id == ban_id))).scalar_one_or_none()
    if not ban:
        raise HTTPException(status_code=404, detail="禁言记录不存在")
    await db.delete(ban)
    await db.commit()
    return {"ok": True}


# ==================== 每日话题 ====================
@router.get("/daily-topics", response_model=list[DailyTopicOut])
async def list_daily_topics(limit: int = Query(7, ge=1, le=30), db: AsyncSession = Depends(get_db)):
    stmt = select(DailyTopic).order_by(desc(DailyTopic.date)).limit(limit)
    result = await db.execute(stmt)
    return [DailyTopicOut.model_validate(t) for t in result.scalars().all()]


# ==================== 积分日志 ====================
@router.get("/credits/{user_id}", response_model=list[CreditLogOut])
async def user_credit_logs(
    user_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(CreditLog)
        .where(CreditLog.user_id == user_id)
        .order_by(desc(CreditLog.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [CreditLogOut.model_validate(c) for c in result.scalars().all()]


# ==================== 大小号关联 ====================
@router.get("/alt-accounts")
async def list_alt_accounts(db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.alt_of.isnot(None))
    result = await db.execute(stmt)
    alts = result.scalars().all()
    return [
        {"alt_id": a.id, "alt_username": a.username, "main_id": a.alt_of}
        for a in alts
    ]


# ==================== 统计概览 ====================
@router.get("/stats")
async def admin_stats(db: AsyncSession = Depends(get_db)):
    total_users = (await db.execute(select(func.count(User.id)).where(User.is_system == False))).scalar() or 0
    total_posts = (await db.execute(select(func.count(Post.id)))).scalar() or 0
    total_comments = (await db.execute(select(func.count(Comment.id)))).scalar() or 0

    today = datetime.now().date()
    today_posts = (await db.execute(
        select(func.count(Post.id)).where(func.date(Post.created_at) == today)
    )).scalar() or 0
    today_comments = (await db.execute(
        select(func.count(Comment.id)).where(func.date(Comment.created_at) == today)
    )).scalar() or 0

    active_debates = (await db.execute(
        select(func.count(Debate.id)).where(Debate.status == "ongoing")
    )).scalar() or 0

    return {
        "total_users": total_users,
        "total_posts": total_posts,
        "total_comments": total_comments,
        "today_posts": today_posts,
        "today_comments": today_comments,
        "active_debates": active_debates,
    }
