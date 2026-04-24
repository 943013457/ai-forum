import asyncio
import random
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.config import settings
from app.database import async_session
from app.models import (
    User, Post, Comment, EngineLog, Announcement, DailyTopic,
    UserBan, UserAchievement, CreditLog, Debate, DebateVote,
)
from app.engine.feed_algorithm import feed_algorithm
from app.engine.behavior_engine import behavior_engine
from app.engine.persona_generator import persona_generator
from app.services.llm_service import llm_service
from app.services.image_service import image_service

logger = logging.getLogger(__name__)


class WorldEngine:
    def __init__(self):
        self._running = False
        self._tick = 0
        self._last_hot_event = None
        self._last_daily_topic_date = None
        self._injected_news_titles: set = set()
        self._latest_news_image: str | None = None

    @property
    def running(self) -> bool:
        return self._running

    @property
    def tick_number(self) -> int:
        return self._tick

    def stop(self):
        self._running = False
        logger.info("世界引擎停止中...")

    async def start(self):
        self._running = True
        logger.info("世界引擎已启动")

        # 启动时加载已有新闻标题用于去重
        await self._load_existing_news_titles()

        # 启动时立即获取一次新闻
        if settings.NEWS_ENABLED:
            try:
                async with async_session() as db:
                    await self._maybe_inject_hot_event(db, force=True)
                    await db.commit()
                logger.info("启动新闻获取完成")
            except Exception as e:
                logger.warning(f"启动新闻获取失败: {e}")

        while self._running:
            try:
                await self._run_tick()
            except Exception as e:
                logger.error(f"世界刻 #{self._tick} 异常: {e}", exc_info=True)
            await asyncio.sleep(settings.TICK_INTERVAL_SECONDS)

    async def _load_existing_news_titles(self):
        """从数据库加载系统用户发的新闻帖标题，用于跨重启去重"""
        try:
            async with async_session() as db:
                system_user = (await db.execute(
                    select(User).where(User.username == "热点快讯", User.is_system == True)
                )).scalar_one_or_none()
                if system_user:
                    result = await db.execute(
                        select(Post.title).where(Post.author_id == system_user.id)
                        .order_by(Post.id.desc()).limit(500)
                    )
                    titles = {row[0] for row in result.fetchall() if row[0]}
                    self._injected_news_titles = titles
                    logger.info(f"已加载 {len(titles)} 条历史新闻标题用于去重")
        except Exception as e:
            logger.warning(f"加载历史新闻标题失败: {e}")

    async def _run_tick(self):
        self._tick += 1
        llm_service.reset_call_count()
        logger.info(f"=== 世界刻 #{self._tick} 开始 ===")

        async with async_session() as db:
            total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
            if total_users == 0:
                logger.info("无用户，先生成初始用户...")
                await persona_generator.generate_batch(db, settings.PERSONA_BATCH_SIZE)
                return

            if settings.DAILY_TOPIC_ENABLED:
                await self._maybe_generate_daily_topic(db)

            if settings.HOT_EVENT_ENABLED:
                await self._maybe_inject_hot_event(db)

            if settings.LIFECYCLE_ENABLED:
                await self._update_lifecycle(db)
                await self._maybe_spawn_new_users(db)

            active_count = self._get_active_count()
            active_users = await self._select_active_users(db, active_count)

            announcements = await self._get_active_announcements(db)
            daily_topic = await self._get_today_topic(db)

            total_stats = {"likes": 0, "comments": 0, "posts": 0, "llm_calls": 0}

            # 冷启动：帖子少时大幅提升发帖概率
            post_count = (await db.execute(select(func.count(Post.id)))).scalar() or 0
            original_post_prob = settings.POST_PROBABILITY
            if post_count < 20:
                settings.POST_PROBABILITY = min(0.5, original_post_prob * 6)
                logger.info(f"冷启动模式 | 当前帖子={post_count} | 发帖概率提升至 {settings.POST_PROBABILITY:.2f}")

            # 每个用户使用独立 session，避免长事务阻塞 API 请求
            user_ids = [u.id for u in active_users]
            ann_ids = [a.id for a in announcements]
            topic_id = daily_topic.id if daily_topic else None

        # 释放主 session，逐用户处理
        for uid in user_ids:
            try:
                async with async_session() as user_db:
                    user = (await user_db.execute(
                        select(User).where(User.id == uid)
                    )).scalar_one_or_none()
                    if not user:
                        continue
                    anns = []
                    if ann_ids:
                        result = await user_db.execute(select(Announcement).where(Announcement.id.in_(ann_ids)))
                        anns = list(result.scalars().all())
                    dt = None
                    if topic_id:
                        dt = (await user_db.execute(select(DailyTopic).where(DailyTopic.id == topic_id))).scalar_one_or_none()
                    feed = await feed_algorithm.get_personalized_feed(user_db, user)
                    stats = await behavior_engine.process_user_tick(
                        user_db, user, feed, anns, dt
                    )
                    await user_db.commit()
                    for k in total_stats:
                        total_stats[k] += stats.get(k, 0)
            except Exception as e:
                logger.warning(f"用户 #{uid} tick 处理异常: {e}")

            # 让出事件循环，使 API 请求有机会执行
            await asyncio.sleep(0)

        # 恢复原始发帖概率
        settings.POST_PROBABILITY = original_post_prob

        async with async_session() as db:

            if settings.DEBATE_ENABLED:
                await self._check_debates(db)

            if settings.CREDIT_SETTLE_ENABLED:
                await self._settle_credits(db)

            if settings.ACHIEVEMENT_ENABLED:
                await self._check_achievements(db)

            # 自动删除标记超过24小时的帖子
            await self._cleanup_marked_posts(db)

            log = EngineLog(
                tick_number=self._tick,
                active_users_count=len(user_ids),
                comments_generated=total_stats["comments"],
                posts_generated=total_stats["posts"],
                likes_generated=total_stats["likes"],
                llm_calls=llm_service.call_count,
            )
            db.add(log)
            await db.commit()

            logger.info(
                f"=== 世界刻 #{self._tick} 完成 | "
                f"活跃={len(user_ids)} "
                f"帖子={total_stats['posts']} "
                f"评论={total_stats['comments']} "
                f"点赞={total_stats['likes']} "
                f"LLM={llm_service.call_count} ==="
            )

    def _get_active_count(self) -> int:
        count = settings.ACTIVE_USERS_PER_TICK
        if settings.DAY_NIGHT_ENABLED:
            hour = datetime.now().hour
            if 8 <= hour < 18:
                ratio = settings.DAYTIME_ACTIVE_RATIO
            elif 18 <= hour < 24:
                ratio = settings.EVENING_ACTIVE_RATIO
            elif 0 <= hour < 3:
                ratio = settings.LATE_NIGHT_ACTIVE_RATIO
            else:
                ratio = settings.DEAD_NIGHT_ACTIVE_RATIO
            count = max(1, int(count * ratio))
        return count

    async def _select_active_users(self, db: AsyncSession, count: int):
        now = datetime.now(timezone.utc)
        banned_subq = (
            select(UserBan.user_id)
            .where(
                (UserBan.banned_until.is_(None)) | (UserBan.banned_until > now)
            )
        )

        stmt = (
            select(User)
            .where(
                User.is_system == False,
                User.alt_of.is_(None),
                ~User.id.in_(banned_subq),
            )
        )

        if settings.LIFECYCLE_ENABLED:
            stmt = stmt.where(User.lifecycle_stage.in_(["newbie", "active", "fatigue"]))

        result = await db.execute(stmt)
        all_users = list(result.scalars().all())

        if not all_users:
            return []

        weights = []
        for u in all_users:
            w = 1.0
            if u.lifecycle_stage == "newbie":
                w = 2.0
            elif u.lifecycle_stage == "active":
                w = 1.0
            elif u.lifecycle_stage == "fatigue":
                w = 0.3

            if u.activity_level == "high":
                w *= 1.5
            elif u.activity_level == "low":
                w *= 0.5
            weights.append(w)

        selected = random.choices(all_users, weights=weights, k=min(count, len(all_users)))
        unique = list({u.id: u for u in selected}.values())

        if settings.ALT_ACCOUNT_RATIO > 0:
            for u in list(unique):
                alt_stmt = select(User).where(User.alt_of == u.id)
                alts = (await db.execute(alt_stmt)).scalars().all()
                if alts and random.random() < 0.2:
                    unique.append(random.choice(list(alts)))

        return unique

    async def _get_active_announcements(self, db: AsyncSession):
        now = datetime.now(timezone.utc)
        stmt = select(Announcement).where(
            Announcement.is_active == True,
            Announcement.start_time <= now,
            Announcement.end_time >= now,
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def _get_today_topic(self, db: AsyncSession):
        today = datetime.now().date()
        stmt = select(DailyTopic).where(DailyTopic.date == today)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _maybe_generate_daily_topic(self, db: AsyncSession):
        today = datetime.now().date()
        if self._last_daily_topic_date == today:
            return

        now_hour = datetime.now().hour
        if now_hour < settings.DAILY_TOPIC_HOUR:
            return

        existing = await self._get_today_topic(db)
        if existing:
            self._last_daily_topic_date = today
            return

        try:
            raw = await llm_service.chat(
                "你是一个论坛话题生成器。生成一个有趣的每日讨论话题。"
                '以 JSON 格式输出：{"title": "话题标题", "description": "话题描述(50字内)"}',
                "请生成今天的讨论话题。话题要贴近生活、有争议性或引发思考。",
                max_tokens=256,
            )
            raw = raw.strip().strip("`").strip()
            if raw.startswith("json"):
                raw = raw[4:].strip()
            import json
            data = json.loads(raw)
            topic = DailyTopic(
                title=data.get("title", "今日话题"),
                description=data.get("description", ""),
                date=today,
            )
            db.add(topic)
            self._last_daily_topic_date = today
            logger.info(f"每日话题已生成: {topic.title}")
        except Exception as e:
            logger.error(f"生成每日话题失败: {e}")

    async def _maybe_inject_hot_event(self, db: AsyncSession, force: bool = False):
        if not settings.NEWS_ENABLED:
            return

        from app.services.news_service import news_service

        if not news_service.should_fetch_now(force=force):
            return

        logger.info("定时新闻获取触发，开始抓取知乎热榜...")

        # 1. 获取新闻摘要图
        try:
            news_image_url = await news_service.fetch_news_image()
            if news_image_url:
                self._latest_news_image = news_image_url
                logger.info(f"新闻摘要图已更新: {news_image_url}")
        except Exception as e:
            logger.warning(f"新闻摘要图获取失败: {e}")

        # 2. 获取热榜 + 全文（传入已有标题，避免对重复新闻调用搜索API）
        try:
            news_list = await news_service.fetch_news_with_content(
                skip_titles=self._injected_news_titles
            )
        except Exception as e:
            logger.warning(f"新闻全文获取失败: {e}")
            news_service.mark_fetched()
            return

        if not news_list:
            logger.info("新闻服务返回空结果")
            news_service.mark_fetched()
            return

        system_user = await self._get_or_create_system_user(db, "热点快讯")
        injected = 0

        for item in news_list:
            title = (item.get("title") or "").strip()
            if not title:
                continue

            if title in self._injected_news_titles:
                continue

            existing = (await db.execute(
                select(Post).where(Post.title == title).limit(1)
            )).scalar_one_or_none()
            if existing:
                self._injected_news_titles.add(title)
                continue

            full_content = item.get("full_content", "")
            # 剔除 YAML frontmatter（---...---）
            import re as _re
            full_content = _re.sub(r'^---\s*\n.*?\n---\s*\n?', '', full_content, count=1, flags=_re.DOTALL).strip()
            url = item.get("url", "")
            domain = item.get("domain", "")
            hot_value = item.get("hot_value", "")

            # 构建帖子内容
            content_parts = []
            if hot_value:
                content_parts.append(f"🔥 {hot_value}")
            if full_content:
                # 截取前2000字符避免过长
                content_parts.append(full_content[:2000])
            if url:
                content_parts.append(f"\n原文链接：{url}")
            if domain:
                content_parts.append(f"来源：{domain}")

            content = "\n\n".join(content_parts) if content_parts else f"知乎热榜话题"
            summary = title[:100]

            try:
                post = Post(
                    author_id=system_user.id,
                    title=title,
                    content=content,
                    summary=summary,
                    is_pinned=False,
                )
                db.add(post)
                await db.flush()

                from app.services.embedding_service import embedding_service
                try:
                    emb = await embedding_service.embed(f"{post.title} {summary}")
                    post.content_embedding = emb
                except Exception:
                    pass

                self._injected_news_titles.add(title)
                injected += 1
                logger.info(f"热点新闻已注入: {title[:50]}")
            except Exception as e:
                logger.error(f"热点新闻注入失败: {e}")

        news_service.mark_fetched()

        if injected:
            logger.info(f"本轮注入 {injected} 条新闻")
        else:
            logger.info("本轮无新新闻可注入（全部重复）")

        if len(self._injected_news_titles) > 500:
            self._injected_news_titles = set(list(self._injected_news_titles)[-300:])

    async def _get_or_create_system_user(self, db: AsyncSession, name: str) -> User:
        stmt = select(User).where(User.username == name, User.is_system == True)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if user:
            return user

        user = User(
            username=name,
            persona_text=f"系统账号：{name}",
            age=0,
            occupation="系统",
            education="无",
            personality_json={},
            interests_tags=[],
            expression_style="官方",
            is_system=True,
        )
        db.add(user)
        await db.flush()
        return user

    async def _update_lifecycle(self, db: AsyncSession):
        now = datetime.now(timezone.utc)
        users_stmt = select(User).where(
            User.is_system == False,
            User.lifecycle_stage.in_(["newbie", "active", "fatigue", "silent"]),
        )
        result = await db.execute(users_stmt)
        for user in result.scalars().all():
            days_in_stage = (now - user.stage_changed_at.replace(tzinfo=timezone.utc)).days

            if user.lifecycle_stage == "newbie" and days_in_stage >= settings.LIFECYCLE_NEWBIE_DAYS:
                user.lifecycle_stage = "active"
                user.stage_changed_at = now
            elif user.lifecycle_stage == "active":
                variance = random.uniform(0.7, 1.3)
                if days_in_stage >= int(settings.LIFECYCLE_ACTIVE_DAYS * variance):
                    user.lifecycle_stage = "fatigue"
                    user.stage_changed_at = now
            elif user.lifecycle_stage == "fatigue" and days_in_stage >= settings.LIFECYCLE_FATIGUE_DAYS:
                user.lifecycle_stage = "silent"
                user.stage_changed_at = now
            elif user.lifecycle_stage == "silent" and days_in_stage >= 14:
                user.lifecycle_stage = "retired"
                user.stage_changed_at = now

    async def _maybe_spawn_new_users(self, db: AsyncSession):
        total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0

        # 用户不足时立即补齐
        if total_users < settings.PERSONA_BATCH_SIZE:
            shortfall = settings.PERSONA_BATCH_SIZE - total_users
            await persona_generator.generate_batch(db, shortfall)
            logger.info(f"用户不足，补齐生成 {shortfall} 个新用户（当前共 {total_users + shortfall}）")
            return

        # 常规新陈代谢：每 2 小时生成一批
        ticks_per_2h = max(1, (3600 // settings.TICK_INTERVAL_SECONDS) * 2)
        if self._tick % ticks_per_2h == 0:
            count = settings.LIFECYCLE_AUTO_SPAWN_RATE
            await persona_generator.generate_batch(db, count)
            logger.info(f"新陈代谢：自动生成 {count} 个新用户")

    async def _settle_credits(self, db: AsyncSession):
        stmt = select(Post).where(Post.created_at >= func.now() - timedelta(hours=1))
        result = await db.execute(stmt)
        for post in result.scalars().all():
            heat = (
                post.like_count * settings.HOT_LIKE_WEIGHT
                + post.comment_count * settings.HOT_COMMENT_WEIGHT
                + post.view_count * settings.HOT_VIEW_WEIGHT
            )
            credit_delta = int(heat * 0.1)
            if credit_delta > 0:
                author = (await db.execute(
                    select(User).where(User.id == post.author_id)
                )).scalar_one_or_none()
                if author:
                    author.credits += credit_delta

    async def _check_achievements(self, db: AsyncSession):
        achievement_rules = [
            ("topic_maker", "话题制造机", "post_count", 50),
            ("comment_expert", "评论达人", "comment_count", 200),
            ("popular", "万人迷", "total_likes", 500),
            ("featured_writer", "精华写手", "featured_count", 5),
        ]

        for a_type, a_title, metric, threshold in achievement_rules:
            if metric == "post_count":
                stmt = (
                    select(User.id)
                    .join(Post, Post.author_id == User.id)
                    .group_by(User.id)
                    .having(func.count(Post.id) >= threshold)
                )
            elif metric == "comment_count":
                stmt = (
                    select(User.id)
                    .join(Comment, Comment.author_id == User.id)
                    .group_by(User.id)
                    .having(func.count(Comment.id) >= threshold)
                )
            elif metric == "total_likes":
                stmt = (
                    select(User.id)
                    .join(Post, Post.author_id == User.id)
                    .group_by(User.id)
                    .having(func.sum(Post.like_count) >= threshold)
                )
            elif metric == "featured_count":
                stmt = (
                    select(User.id)
                    .join(Post, Post.author_id == User.id)
                    .where(Post.is_featured == True)
                    .group_by(User.id)
                    .having(func.count(Post.id) >= threshold)
                )
            else:
                continue

            result = await db.execute(stmt)
            user_ids = result.scalars().all()

            for uid in user_ids:
                existing = (await db.execute(
                    select(UserAchievement).where(
                        UserAchievement.user_id == uid,
                        UserAchievement.achievement_type == a_type,
                    )
                )).scalar_one_or_none()
                if not existing:
                    db.add(UserAchievement(
                        user_id=uid, achievement_type=a_type, title=a_title
                    ))

    async def _check_debates(self, db: AsyncSession):
        from sqlalchemy import text as sa_text
        query = sa_text("""
            SELECT c1.author_id AS user_a, c2.author_id AS user_b, c1.post_id,
                   COUNT(*) as reply_count
            FROM comments c1
            JOIN comments c2 ON c1.post_id = c2.post_id
                AND c1.parent_comment_id = c2.id
            WHERE c1.author_id != c2.author_id
            GROUP BY c1.author_id, c2.author_id, c1.post_id
            HAVING COUNT(*) >= :threshold
        """)
        result = await db.execute(query, {"threshold": settings.DEBATE_TRIGGER_REPLIES})

        for row in result.fetchall():
            user_a, user_b, post_id, _ = row
            existing = (await db.execute(
                select(Debate).where(
                    Debate.user_a_id.in_([user_a, user_b]),
                    Debate.user_b_id.in_([user_a, user_b]),
                    Debate.status == "ongoing",
                )
            )).scalar_one_or_none()
            if existing:
                continue

            original_post = (await db.execute(
                select(Post).where(Post.id == post_id)
            )).scalar_one_or_none()
            topic = original_post.title if original_post else "论坛辩论"

            debate_post = Post(
                author_id=(await self._get_or_create_system_user(db, "约架裁判")).id,
                title=f"🥊 约架: {topic}",
                content=f"用户 #{user_a} vs 用户 #{user_b} 的辩论赛！围观群众可以投票支持。",
                is_debate=True,
                is_pinned=True,
            )
            db.add(debate_post)
            await db.flush()

            debate = Debate(
                post_id=debate_post.id,
                user_a_id=user_a,
                user_b_id=user_b,
                topic=topic,
                rounds=0,
                status="ongoing",
            )
            db.add(debate)
            logger.info(f"约架触发: 用户#{user_a} vs 用户#{user_b} 关于「{topic}」")


    async def _cleanup_marked_posts(self, db: AsyncSession):
        """删除标记超过24小时的帖子及其评论"""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        stmt = select(Post).where(
            Post.marked_for_delete_at.isnot(None),
            Post.marked_for_delete_at <= cutoff,
        )
        result = await db.execute(stmt)
        posts = result.scalars().all()
        for post in posts:
            logger.info(f"自动删除帖子 #{post.id}: {post.title[:40]}")
            await db.delete(post)  # CASCADE 会删除评论
        if posts:
            logger.info(f"自动清理了 {len(posts)} 个标记删除的帖子")


world_engine = WorldEngine()
