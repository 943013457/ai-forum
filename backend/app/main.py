import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from sqlalchemy import text
from app.database import engine, Base
from app.api import posts, users, comments, tags, admin

# ==================== 日志配置 ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)-28s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("ai_forum.log", encoding="utf-8"),
    ],
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

logger = logging.getLogger("ai_forum.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.engine.world_engine import world_engine

    logger.info("=" * 60)
    logger.info("AI 论坛世界引擎启动中...")
    logger.info(f"数据库: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
    logger.info(f"LLM: {settings.LLM_API_BASE_URL} (模型: {settings.LLM_MODEL_NAME})")
    logger.info(f"Embedding: {settings.EMBEDDING_API_BASE_URL} (模型: {settings.EMBEDDING_MODEL})")
    logger.info(f"生图: {settings.IMAGE_GEN_API_BASE_URL} (模型: {settings.IMAGE_GEN_MODEL})")
    logger.info(f"视觉: {settings.VISION_API_BASE_URL} (模型: {settings.VISION_MODEL})")
    logger.info(f"Tick 间隔: {settings.TICK_INTERVAL_SECONDS}s | 每刻活跃: {settings.ACTIVE_USERS_PER_TICK}")
    logger.info(f"LLM 限速: {settings.MAX_LLM_CALLS_PER_HOUR}/h")
    logger.info(f"头像模式: {settings.AVATAR_MODE.upper()} ({'UapiPro随机图' if settings.AVATAR_MODE == 'api' else '生图模型'}) | 尺寸≤{settings.AVATAR_MAX_SIZE}px")
    logger.info(f"新闻热榜: {'✅ 定时 ' + settings.NEWS_SCHEDULE_HOURS + ' 点' if settings.NEWS_ENABLED else '❌ 已禁用'}")
    logger.info("=" * 60)

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    logger.info("数据库表创建/验证完成")

    task = asyncio.create_task(world_engine.start())
    yield

    logger.info("正在关闭世界引擎...")
    world_engine.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("世界引擎已关闭")


app = FastAPI(
    title="AI 论坛世界引擎",
    description="生成式智能体社会 - AI 多智能体论坛系统",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
os.makedirs(settings.AVATAR_DIR, exist_ok=True)
os.makedirs(settings.POST_IMAGE_DIR, exist_ok=True)
os.makedirs(settings.NEWS_IMAGE_DIR, exist_ok=True)
app.mount("/static/avatars", StaticFiles(directory=settings.AVATAR_DIR), name="avatars")
app.mount("/static/post_images", StaticFiles(directory=settings.POST_IMAGE_DIR), name="post_images")
app.mount("/static/news_images", StaticFiles(directory=settings.NEWS_IMAGE_DIR), name="news_images")

app.include_router(posts.router, prefix="/api/posts", tags=["帖子"])
app.include_router(users.router, prefix="/api/users", tags=["用户"])
app.include_router(comments.router, prefix="/api/comments", tags=["评论"])
app.include_router(tags.router, prefix="/api/tags", tags=["标签"])
app.include_router(admin.router, prefix="/api/admin", tags=["管理"])


@app.middleware("http")
async def log_requests(request: Request, call_next):
    import time
    start = time.time()
    response = await call_next(request)
    elapsed = (time.time() - start) * 1000
    if not request.url.path.startswith("/api/health"):
        logger.info(f"{request.method} {request.url.path} → {response.status_code} ({elapsed:.0f}ms)")
    return response


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "AI 论坛世界引擎"}


@app.get("/api/announcements/active")
async def active_announcements():
    """公开接口：获取进行中的公告"""
    from app.database import async_session
    from app.models import Announcement
    from sqlalchemy import select, desc
    from datetime import datetime, timezone
    async with async_session() as db:
        now = datetime.now(timezone.utc)
        stmt = (
            select(Announcement)
            .where(Announcement.is_active == True, Announcement.end_time > now)
            .order_by(desc(Announcement.created_at))
            .limit(5)
        )
        result = await db.execute(stmt)
        anns = result.scalars().all()
        return [
            {
                "id": a.id, "title": a.title, "content": a.content,
                "reward_credits": a.reward_credits,
                "end_time": a.end_time.isoformat(),
            }
            for a in anns
        ]


@app.get("/api/news-image")
async def get_news_image():
    """获取最新的每日新闻摘要图 URL"""
    from app.engine.world_engine import world_engine
    image_url = world_engine._latest_news_image

    # 如果引擎还没抓过，尝试找磁盘上最新的文件
    if not image_url:
        import glob
        pattern = os.path.join(settings.NEWS_IMAGE_DIR, "news_*.jpg")
        files = sorted(glob.glob(pattern), reverse=True)
        if files:
            image_url = f"/static/news_images/{os.path.basename(files[0])}"

    return {"image_url": image_url}
