import datetime
from typing import Optional, List

from pydantic import BaseModel


# ==================== 用户 ====================
class UserBase(BaseModel):
    username: str
    age: int
    occupation: str
    education: str
    language: str = "zh"
    activity_level: str = "medium"


class UserOut(UserBase):
    id: int
    avatar_url: Optional[str] = None
    persona_text: str
    personality_json: dict
    interests_tags: list
    expression_style: str
    credits: int
    mood: float
    lifecycle_stage: str
    alt_of: Optional[int] = None
    is_system: bool = False
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class UserBrief(BaseModel):
    id: int
    username: str
    avatar_url: Optional[str] = None
    credits: int
    lifecycle_stage: str
    occupation: Optional[str] = None
    interests_tags: Optional[list] = None

    model_config = {"from_attributes": True}


class UserProfile(UserOut):
    follower_count: int = 0
    following_count: int = 0
    post_count: int = 0
    comment_count: int = 0
    achievements: List["AchievementOut"] = []
    ban_status: Optional["BanOut"] = None


# ==================== 帖子 ====================
class PostCreate(BaseModel):
    title: str
    content: Optional[str] = None


class PostOut(BaseModel):
    id: int
    author_id: int
    title: str
    content: Optional[str] = None
    summary: Optional[str] = None
    image_url: Optional[str] = None
    image_description: Optional[str] = None
    is_featured: bool = False
    is_pinned: bool = False
    is_rumor: bool = False
    is_poll: bool = False
    is_debate: bool = False
    is_repost: bool = False
    repost_of: Optional[int] = None
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    marked_for_delete_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    author: Optional[UserBrief] = None
    tags: List[str] = []

    model_config = {"from_attributes": True}


class PostDetail(PostOut):
    comments: List["CommentOut"] = []
    poll: Optional["PollOut"] = None


# ==================== 评论 ====================
class CommentCreate(BaseModel):
    content: str
    parent_comment_id: Optional[int] = None


class CommentOut(BaseModel):
    id: int
    post_id: int
    author_id: int
    content: str
    parent_comment_id: Optional[int] = None
    created_at: datetime.datetime
    author: Optional[UserBrief] = None
    replies: List["CommentOut"] = []

    model_config = {"from_attributes": True}


# ==================== 标签 ====================
class TagOut(BaseModel):
    id: int
    name: str
    post_count: int = 0

    model_config = {"from_attributes": True}


# ==================== 公告 ====================
class AnnouncementCreate(BaseModel):
    title: str
    content: str
    reward_credits: int = 0
    required_tags: Optional[list] = None
    start_time: datetime.datetime
    end_time: datetime.datetime


class AnnouncementOut(BaseModel):
    id: int
    title: str
    content: str
    reward_credits: int
    required_tags: Optional[list] = None
    start_time: datetime.datetime
    end_time: datetime.datetime
    is_active: bool
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# ==================== 禁言 ====================
class BanCreate(BaseModel):
    user_id: int
    reason: str
    duration: Optional[str] = None  # "24h", "3d", "7d", "30d", "permanent"


class BanOut(BaseModel):
    id: int
    user_id: int
    reason: str
    banned_until: Optional[datetime.datetime] = None
    created_by: Optional[str] = None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# ==================== 投票 ====================
class PollOut(BaseModel):
    id: int
    post_id: int
    options: list
    votes: dict = {}  # {option_index: count}
    total_votes: int = 0

    model_config = {"from_attributes": True}


class PollVoteCreate(BaseModel):
    option_index: int


# ==================== 约架 ====================
class DebateOut(BaseModel):
    id: int
    post_id: int
    user_a_id: int
    user_b_id: int
    topic: str
    rounds: int
    winner_id: Optional[int] = None
    status: str
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# ==================== 成就 ====================
class AchievementOut(BaseModel):
    achievement_type: str
    title: str
    awarded_at: datetime.datetime

    model_config = {"from_attributes": True}


# ==================== 每日话题 ====================
class DailyTopicOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    date: datetime.date
    post_count: int
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# ==================== 引擎日志 ====================
class EngineLogOut(BaseModel):
    id: int
    tick_number: int
    active_users_count: int
    comments_generated: int
    posts_generated: int
    likes_generated: int
    llm_calls: int
    timestamp: datetime.datetime

    model_config = {"from_attributes": True}


# ==================== 引擎状态 ====================
class EngineStatus(BaseModel):
    running: bool
    tick_number: int
    total_users: int
    total_posts: int
    total_comments: int
    llm_calls_this_hour: int


# ==================== 积分日志 ====================
class CreditLogOut(BaseModel):
    id: int
    user_id: int
    amount: int
    reason: str
    related_post_id: Optional[int] = None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# ==================== 分页 ====================
class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    pages: int
