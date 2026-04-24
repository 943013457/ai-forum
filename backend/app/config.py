from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional

# 自动查找 .env：先找 backend/.env，再找项目根目录 ../.env
_backend_dir = Path(__file__).resolve().parent.parent  # backend/
_env_candidates = [_backend_dir / ".env", _backend_dir.parent / ".env"]
_env_file = next((p for p in _env_candidates if p.exists()), ".env")


class Settings(BaseSettings):
    # ==================== 数据库配置 ====================
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "ai_forum"
    POSTGRES_USER: str = "ai_forum"
    POSTGRES_PASSWORD: str = "changeme"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ==================== LLM 大语言模型 ====================
    LLM_API_BASE_URL: str = "http://localhost:8080/v1"
    LLM_API_KEY: str = "your-llm-api-key"
    LLM_MODEL_NAME: str = "hermes"

    # ==================== Embedding 向量嵌入模型 ====================
    EMBEDDING_API_BASE_URL: str = "https://api.siliconflow.cn/v1"
    EMBEDDING_API_KEY: str = "your-embedding-api-key"
    EMBEDDING_MODEL: str = "BAAI/bge-m3"

    # ==================== 图像生成 ====================
    IMAGE_GEN_API_BASE_URL: str = "https://api.siliconflow.cn/v1"
    IMAGE_GEN_API_KEY: str = "your-image-gen-api-key"
    IMAGE_GEN_MODEL: str = "Kwai-Kolors/Kolors"
    IMAGE_SIZE: str = "1024x1024"
    IMAGE_INFERENCE_STEPS: int = 20
    IMAGE_GUIDANCE_SCALE: float = 7.5

    # ==================== 视觉识别模型 ====================
    VISION_API_BASE_URL: str = "https://api.siliconflow.cn/v1"
    VISION_API_KEY: str = "your-vision-api-key"
    VISION_MODEL: str = "Qwen/Qwen3.5-4B"

    # ==================== 世界引擎节奏 ====================
    TICK_INTERVAL_SECONDS: int = 90
    ACTIVE_USERS_PER_TICK: int = 50
    MAX_LLM_CALLS_PER_HOUR: int = 400

    # ==================== AI 用户行为概率 ====================
    COMMENT_PROBABILITY: float = 0.12
    POST_PROBABILITY: float = 0.02
    POST_IMAGE_PROBABILITY: float = 0.10
    IMAGE_ONLY_POST_PROBABILITY: float = 0.03
    LIKE_BASE_PROBABILITY: float = 0.25
    ENTROPY_RATIO: float = 0.05

    # ==================== 文章/评论字数 ====================
    POST_MIN_LENGTH: int = 200
    POST_MAX_LENGTH: int = 500
    COMMENT_MIN_LENGTH: int = 50
    COMMENT_MAX_LENGTH: int = 200

    # ==================== 推荐算法权重 ====================
    FEED_MATCH_WEIGHT: float = 0.60
    FEED_HOT_WEIGHT: float = 0.25
    FEED_CREDIT_WEIGHT: float = 0.15
    FEED_TOP_N: int = 5

    # ==================== 热度公式参数 ====================
    HOT_LIKE_WEIGHT: float = 2.0
    HOT_COMMENT_WEIGHT: float = 5.0
    HOT_VIEW_WEIGHT: float = 0.1
    HOT_DECAY_POWER: float = 1.5

    # ==================== 积分系统 ====================
    FEATURED_POST_REWARD: int = 50
    CREDIT_SETTLE_ENABLED: bool = True

    # ==================== AI 用户生成参数 ====================
    PERSONA_MIN_AGE: int = 15
    PERSONA_MAX_AGE: int = 80
    PERSONA_BATCH_SIZE: int = 50

    # ==================== 关系网络 ====================
    AUTO_FOLLOW_INTERACTION_THRESHOLD: int = 3
    FOLLOW_FEED_BOOST: float = 1.5

    # ==================== 情绪系统 ====================
    MOOD_ENABLED: bool = True
    MOOD_DECAY_RATE: float = 0.05

    # ==================== UapiPro 服务 ====================
    UAPI_BASE_URL: str = "https://uapis.cn/api/v1"
    UAPI_KEY: str = ""

    # ==================== 头像生成模式 ====================
    AVATAR_MODE: str = "api"  # "api" 使用 UapiPro 随机图片, "model" 使用生图模型
    AVATAR_MAX_SIZE: int = 256  # 头像压缩后最大边长(像素)
    AVATAR_QUALITY: int = 80    # JPEG 压缩质量

    # ==================== 新闻热榜 ====================
    NEWS_ENABLED: bool = True
    NEWS_SCHEDULE_HOURS: str = "8,12,15,18,20,0"  # 定时获取新闻的小时列表
    NEWS_TOP_N: int = 5  # 每次获取知乎热榜前N条

    # ==================== 热点事件注入 ====================
    HOT_EVENT_ENABLED: bool = True

    # ==================== 每日话题 ====================
    DAILY_TOPIC_ENABLED: bool = True
    DAILY_TOPIC_HOUR: int = 8
    DAILY_TOPIC_PARTICIPATION_RATE: float = 0.30

    # ==================== 公告活动 ====================
    ANNOUNCEMENT_MAX_REWARD: int = 300
    ANNOUNCEMENT_MIN_PARTICIPATION: float = 0.05
    ANNOUNCEMENT_MAX_PARTICIPATION: float = 0.50

    # ==================== 称号/成就系统 ====================
    ACHIEVEMENT_ENABLED: bool = True

    # ==================== 用户生命周期 ====================
    LIFECYCLE_ENABLED: bool = True
    LIFECYCLE_NEWBIE_DAYS: int = 7
    LIFECYCLE_ACTIVE_DAYS: int = 30
    LIFECYCLE_FATIGUE_DAYS: int = 20
    LIFECYCLE_AUTO_SPAWN_RATE: int = 5

    # ==================== 昼夜节律 ====================
    DAY_NIGHT_ENABLED: bool = True
    DAYTIME_ACTIVE_RATIO: float = 1.0
    EVENING_ACTIVE_RATIO: float = 0.8
    LATE_NIGHT_ACTIVE_RATIO: float = 0.2
    DEAD_NIGHT_ACTIVE_RATIO: float = 0.05

    # ==================== 谣言传播 ====================
    RUMOR_ENABLED: bool = True
    RUMOR_SPREAD_PROBABILITY: float = 0.15
    RUMOR_DEBUNK_PROBABILITY: float = 0.30

    # ==================== 投票帖 ====================
    POLL_POST_PROBABILITY: float = 0.05
    POLL_MAX_OPTIONS: int = 4

    # ==================== 对线/约架 ====================
    DEBATE_ENABLED: bool = True
    DEBATE_TRIGGER_REPLIES: int = 3
    DEBATE_ROUNDS: int = 5
    DEBATE_WIN_REWARD: int = 20
    DEBATE_LOSE_PENALTY: int = 10

    # ==================== 多语言用户 ====================
    MULTILANG_ENABLED: bool = True
    FOREIGN_USER_RATIO: float = 0.05

    # ==================== 小号/潜水党 ====================
    ALT_ACCOUNT_RATIO: float = 0.08
    LURKER_RATIO: float = 0.15
    REPOSTER_RATIO: float = 0.10

    # ==================== 存储路径 ====================
    DATA_DIR: str = "./data"
    AVATAR_DIR: str = "./data/avatars"
    POST_IMAGE_DIR: str = "./data/post_images"
    NEWS_IMAGE_DIR: str = "./data/news_images"

    # ==================== 管理员账号 ====================
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "changeme"

    # ==================== 服务端口 ====================
    BACKEND_PORT: int = 8000
    FRONTEND_PORT: int = 3000
    NGINX_PORT: int = 80

    # ==================== JWT ====================
    SECRET_KEY: str = "ai-forum-secret-key-change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    model_config = {"env_file": str(_env_file), "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
