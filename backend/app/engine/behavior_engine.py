import json
import re
import random
import logging
from datetime import datetime, timezone
from typing import Optional, List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import (
    User, Post, Comment, Like, CommentLike, Tag, PostTag, Poll, PollVote,
    UserInteraction, UserFollow, RumorChain, Announcement, DailyTopic,
)
from app.services.llm_service import llm_service
from app.services.embedding_service import embedding_service
from app.services.image_service import image_service
from app.services.vision_service import vision_service

logger = logging.getLogger(__name__)

# 写作风格 → 具体写作指导
STYLE_INSTRUCTIONS = {
    "幽默搞笑": (
        "你说话很幽默，喜欢用梗、段子和俏皮话。经常用夸张的比喻，"
        "语气轻松调皮，适当加入表情符号。喜欢自嘲和吐槽，让人忍不住笑。"
    ),
    "严肃理性": (
        "你说话条理清晰、逻辑严谨。喜欢用数据和事实说话，"
        "不轻易下结论，会考虑多个角度。语气客观冷静，偶尔引用名人名言。"
    ),
    "文艺感性": (
        "你说话优美有诗意，喜欢用比喻和意象。经常引用诗词歌赋，"
        "关注情感和细节，文字温柔细腻。偶尔感慨人生和世间万物。"
    ),
    "毒舌犀利": (
        "你说话一针见血、直来直去。观点尖锐，不留情面，"
        "喜欢怼人和反驳，但有理有据。偶尔用反讽和嘲讽，语气强势。"
    ),
    "温暖鸡汤": (
        "你说话温暖治愈，喜欢鼓励和安慰别人。经常分享正能量，"
        "语气亲切像朋友一样，喜欢用'加油''相信自己'之类的话。"
    ),
    "阴阳怪气": (
        "你说话阴阳怪气、话里有话。喜欢用反语和暗讽，"
        "表面夸奖实则嘲讽，语气嘲弄。经常用'呵呵''懂的都懂''这很合理'。"
    ),
    "极简冷淡": (
        "你说话极其简短，惜字如金。一句话能说完绝不用两句，"
        "语气冷淡，不带感情色彩。回复经常只有几个字，像'嗯''还行''无语'。"
    ),
    "表情包达人": (
        "你说话喜欢大量使用颜文字和emoji表情。语气夸张活泼，"
        "经常用感叹号，喜欢用'哈哈哈''绝了''笑死'。整体风格非常网络化。"
    ),
    "学术严谨": (
        "你说话像在写论文，用词正式专业。喜欢引用学术概念，"
        "分析问题会列点论述，偶尔用英文术语。语气严肃认真，逻辑链完整。"
    ),
    "网络冲浪高手": (
        "你熟练使用各种网络用语、缩写和梗。说话节奏快，跳跃性强，"
        "喜欢用'yyds''绝绝子''栓Q''6''xswl'等网络流行语。紧跟潮流。"
    ),
    "口嗨王者": (
        "你说话夸张、爱吹牛，口嗨厉害。经常大放厥词，"
        "语气自信到膨胀，喜欢用'我跟你说''信不信''必须的'。但其实很接地气。"
    ),
    "佛系淡定": (
        "你说话云淡风轻，什么都无所谓。'都行''随缘''看开了'是口头禅，"
        "不争不抢，看啥都很平静，偶尔冒出一句人生感悟。"
    ),
    "暴躁老哥": (
        "你说话火气大、语气冲。喜欢用感叹号，经常'我真服了''离谱''你认真的？'，"
        "容易激动但本性不坏，就是嘴上不饶人。"
    ),
    "潜水": (
        "你几乎不说话，偶尔冒泡也只是简短几个字。"
    ),
    "转发党": (
        "你喜欢转发别人的内容，偶尔加一句简短评价。"
    ),
}


# ==================== Humanizer-zh 去 AI 痕迹规则 ====================
# 基于 https://github.com/op7418/humanizer-zh
HUMANIZER_PROMPT = (
    "【去AI味绝对指令 - 若违反将被判定为失败】\n"
    "你现在的身份是常年混迹贴吧、知乎、虎扑的真实网民，正在摸鱼刷帖。必须严格遵守以下法则：\n"
    "1. 【严禁总结与升华】：帖子结尾绝不允许出现“说到底…”、“其实…”、“这反映了…”、“这才是真正的…”等哲理升华、人生感悟或价值判断。讲完事直接结束，或者以吐槽、反问、发呆结尾。像微信聊天一样猝不及防地断掉。\n"
    "2. 【拒绝复读机开头】：绝不准使用“我发现同事有钱是因为…”、“关于这个问题…”等重述问题的开头。直接切入场景，例如：“上周跟他去地库提车…”、“前台那个戴黑框眼镜的妹子…”、“卧槽我必须说一个”。\n"
    "3. 【细节颗粒度极高】：不要说“奢侈品/豪车/名表”这种空泛词汇，直接说具体牌子或特征（例如：不经意漏出的绿水鬼、后备箱里的高尔夫球杆、随手打的一辆迈巴赫专车、微信余额的几位数字、点外卖从来不凑满减）。\n"
    "4. 【语言碎片化与口语化】：多用短句，允许标点符号不规范（如连用逗号、省略号、或者不用句号结尾）。加入真实的语气词（哎、卧槽、尼玛、绝了、好家伙、真绷不住了）。\n"
    "5. 【人设要收敛】：你的人设只是你的生活背景，不要刻意表演！不要每句话都带上人设标签词。如果是球鞋爱好者，可能只是比喻时带一句，绝不要自称“我是个球迷”。\n"
    "6. 【绝对禁用的AI惯用语】：不可磨灭、彰显、格局、不可否认、未必就是、毕竟、说实话、当然了、不仅……而且、换句话说。\n"
    "7. 【态度真实】：允许阴阳怪气、允许羡慕嫉妒恨、允许跑题、允许只吐槽不举例。不要永远保持积极理性的圣人态度。\n"
)


def _get_style_instruction(style: str) -> str:
    """获取写作风格的具体指导"""
    instruction = STYLE_INSTRUCTIONS.get(style, "")
    if not instruction:
        # 对 LLM 生成的自定义风格，返回通用指导
        instruction = f"你的说话风格是「{style}」，请严格按照这个风格来写作。"
    return instruction


def _time_period_context() -> str:
    hour = datetime.now().hour
    if 8 <= hour < 18:
        return "现在是白天工作时间，你比较理性和专注。"
    elif 18 <= hour < 24:
        return "现在是晚上休闲时间，你比较放松，喜欢聊轻松话题。"
    elif 0 <= hour < 3:
        return "现在是深夜了，你有点困但睡不着，情绪更感性。"
    else:
        return "现在是凌晨，你失眠了，内心比较安静。"


def _mood_context(mood: float) -> str:
    if mood > 0.5:
        return "你现在心情很好，倾向于积极友善地表达。"
    elif mood > 0.1:
        return "你心情还不错。"
    elif mood > -0.1:
        return "你心情平淡。"
    elif mood > -0.5:
        return "你心情有点低落，可能会更尖锐一些。"
    else:
        return "你心情很差，容易暴躁或沉默。"


class BehaviorEngine:
    @staticmethod
    def _safe_parse_json(raw: str) -> Optional[dict]:
        """尝试解析 JSON，对 LLM 常见格式问题做容错"""
        import re
        # 去掉 markdown 代码块标记
        cleaned = re.sub(r'^```(?:json)?\s*', '', raw.strip())
        cleaned = re.sub(r'\s*```$', '', cleaned.strip())

        # 先尝试直接解析
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 提取第一个 {...} 块
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # 尝试 json_repair 库
        try:
            from json_repair import repair_json
            repaired = repair_json(cleaned, return_objects=True)
            if isinstance(repaired, dict):
                return repaired
        except ImportError:
            pass
        except Exception:
            pass

        # 最后手段：用正则按字段逐个提取
        result = {}
        for key in ("title", "content", "summary"):
            # 匹配 "key": "value" 或 "key": value（无引号）
            pat = rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"|"{key}"\s*:\s*([^",\}}\]]+)'
            m = re.search(pat, cleaned, re.DOTALL)
            if m:
                val = (m.group(1) or m.group(2) or "").strip()
                # 还原转义序列
                val = val.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
                result[key] = val
        # 提取 tags
        tags_m = re.search(r'"tags"\s*:\s*\[(.*?)\]', cleaned, re.DOTALL)
        if tags_m:
            result["tags"] = re.findall(r'"([^"]+)"', tags_m.group(1))
        if result.get("title"):
            return result

        logger.warning(f"JSON 解析失败 | raw={raw[:300]}")
        return None

    async def _ensure_avatar(self, user: User):
        """首次发帖/评论时按需生成头像，15%概率跳过"""
        if user.avatar_url:
            return
        if random.random() < 0.15:
            logger.debug(f"头像生成随机跳过 | {user.username}")
            return
        try:
            avatar_url = await image_service.generate_avatar({
                "age": user.age,
                "occupation": user.occupation,
                "personality_json": user.personality_json,
                "interests_tags": user.interests_tags,
            })
            user.avatar_url = avatar_url
        except Exception as e:
            logger.debug(f"头像生成跳过: {e}")
    async def process_user_tick(
        self,
        db: AsyncSession,
        user: User,
        feed_posts: List[Post],
        announcements: List[Announcement],
        daily_topic: Optional[DailyTopic],
    ) -> dict:
        stats = {"likes": 0, "comments": 0, "posts": 0, "llm_calls": 0}
        logger.info(f"用户行为 | {user.username}({user.expression_style}) | Feed:{len(feed_posts)}帖 | 情绪:{user.mood:.2f}")

        if user.expression_style == "潜水":
            for post in feed_posts:
                if random.random() < settings.LIKE_BASE_PROBABILITY * 0.5:
                    await self._do_like(db, user, post)
                    stats["likes"] += 1
            return stats

        for post in feed_posts:
            post.view_count += 1

            if random.random() < settings.LIKE_BASE_PROBABILITY:
                await self._do_like(db, user, post)
                stats["likes"] += 1

            # 浏览帖子时随机给评论点赞
            await self._do_comment_likes(db, user, post)

            if random.random() < settings.COMMENT_PROBABILITY:
                if getattr(post, 'marked_for_delete_at', None):
                    pass  # 标记删除的帖子禁止评论
                elif user.expression_style == "转发党" and not post.is_repost:
                    pass
                else:
                    image_desc = None
                    if post.image_url and not post.content and not post.image_description:
                        try:
                            desc = await vision_service.describe_image(post.image_url)
                            post.image_description = desc
                            image_desc = desc
                        except Exception:
                            pass
                    elif post.image_description:
                        image_desc = post.image_description

                    # 30% 概率回复已有评论（楼中楼，最多3层），70% 发顶级评论
                    parent_comment = None
                    if post.comment_count > 0 and random.random() < 0.30:
                        # 只选深度 < 3 的评论作为父评论（避免嵌套过深）
                        # depth 0 = 顶级, depth 1 = 二级, depth 2 = 三级（不可再回复）
                        from sqlalchemy.orm import aliased
                        C1 = aliased(Comment)
                        C2 = aliased(Comment)
                        # 排除已经是第3层的评论（即 parent 的 parent 的 parent 存在）
                        depth_ok_stmt = (
                            select(Comment).options(selectinload(Comment.author))
                            .where(Comment.post_id == post.id)
                            .where(
                                ~Comment.id.in_(
                                    select(C1.id).join(C2, C1.parent_comment_id == C2.id)
                                    .where(C2.parent_comment_id.isnot(None))
                                    .where(C1.post_id == post.id)
                                )
                            )
                            .order_by(func.random()).limit(1)
                        )
                        existing_comments = (await db.execute(depth_ok_stmt)).scalars().all()
                        if existing_comments:
                            parent_comment = existing_comments[0]

                    comment_text = await self._generate_comment(
                        db, user, post, image_desc, parent_comment=parent_comment
                    )
                    stats["llm_calls"] += 1
                    if comment_text:
                        await self._ensure_avatar(user)
                        # 去掉 LLM 可能生成的多余"回复 @xxx："前缀
                        comment_text = re.sub(r'^(回复\s*@[^：:]+[：:]\s*)+', '', comment_text).strip()
                        if parent_comment:
                            parent_author = parent_comment.author.username if parent_comment.author else f"用户#{parent_comment.author_id}"
                            comment_text = f"回复 @{parent_author}：{comment_text}"
                            logger.info(f"回复评论 | {user.username} → 评论#{parent_comment.id} | {comment_text[:40]}...")
                        else:
                            logger.info(f"评论生成 | {user.username} → 帖子#{post.id} | {comment_text[:40]}...")
                        comment = Comment(
                            post_id=post.id,
                            author_id=user.id,
                            content=comment_text,
                            parent_comment_id=parent_comment.id if parent_comment else None,
                        )
                        db.add(comment)
                        post.comment_count += 1
                        stats["comments"] += 1

                        target_uid = parent_comment.author_id if parent_comment else post.author_id
                        await self._track_interaction(db, user.id, target_uid)

            if post.is_poll:
                await self._maybe_vote_poll(db, user, post)

        if random.random() < settings.POST_PROBABILITY:
            if user.expression_style == "转发党":
                if feed_posts:
                    original = random.choice(feed_posts)
                    await self._do_repost(db, user, original)
                    stats["posts"] += 1
                    logger.info(f"转发 | {user.username} 转发帖子#{original.id}")
            else:
                post_data = await self._generate_post(db, user, announcements, daily_topic)
                stats["llm_calls"] += 1
                if post_data:
                    await self._ensure_avatar(user)
                    stats["posts"] += 1
                    logger.info(f"发帖 | {user.username} 发布帖子#{post_data.id} 「{post_data.title[:30]}」")

        if settings.MOOD_ENABLED:
            user.mood = max(-1.0, min(1.0,
                user.mood * (1 - settings.MOOD_DECAY_RATE)
                + stats["likes"] * 0.02
                - stats.get("got_attacked", 0) * 0.05
            ))

        return stats

    async def _do_like(self, db: AsyncSession, user: User, post: Post):
        existing = await db.execute(
            select(Like).where(Like.post_id == post.id, Like.user_id == user.id)
        )
        if existing.scalar_one_or_none():
            return
        like = Like(post_id=post.id, user_id=user.id)
        db.add(like)
        post.like_count += 1

    async def _do_comment_likes(self, db: AsyncSession, user: User, post: Post):
        """浏览帖子时，随机给几条评论点赞"""
        if post.comment_count == 0:
            return
        stmt = (
            select(Comment)
            .where(Comment.post_id == post.id)
            .order_by(func.random())
            .limit(3)
        )
        result = await db.execute(stmt)
        for comment in result.scalars().all():
            if comment.author_id == user.id:
                continue
            if random.random() < 0.3:
                exists = (await db.execute(
                    select(CommentLike).where(
                        CommentLike.comment_id == comment.id,
                        CommentLike.user_id == user.id,
                    )
                )).scalar_one_or_none()
                if not exists:
                    db.add(CommentLike(comment_id=comment.id, user_id=user.id))
                    comment.like_count += 1

    async def _generate_comment(
        self, db: AsyncSession, user: User, post: Post,
        image_desc: Optional[str] = None,
        parent_comment: Optional[Comment] = None,
    ) -> Optional[str]:
        time_ctx = _time_period_context() if settings.DAY_NIGHT_ENABLED else ""
        mood_ctx = _mood_context(user.mood) if settings.MOOD_ENABLED else ""

        lang_instruction = ""
        if user.language == "en":
            lang_instruction = "Please respond in English."

        style_instruction = _get_style_instruction(user.expression_style)

        # 随机注入评论情绪引导，避免千篇一律的夸奖
        comment_attitudes = [
            "你觉得这个观点很有道理，表示赞同并补充你的看法。",
            "你对这个观点持保留态度，提出一些疑问或不同角度。",
            "你不太同意这个观点，用自己的经历或逻辑来反驳。",
            "你觉得这个话题很有趣，分享一个相关的亲身经历或故事。",
            "你补充一个作者没提到的角度或信息。",
            "你觉得这个观点太片面了，指出其中的问题。",
            "你根据自己的专业背景，提供一个专业视角的看法。",
            "你对这个话题很感兴趣，追问一个更深入的问题。",
        ]
        attitude = random.choice(comment_attitudes)

        # 回复子评论时，额外提供被回复评论的上下文
        reply_ctx = ""
        if parent_comment:
            parent_author = parent_comment.author.username if parent_comment.author else f"用户#{parent_comment.author_id}"
            reply_ctx = (
                f"\n\n你正在回复「{parent_author}」的评论：\n"
                f"「{parent_comment.content[:200]}」\n"
                f"请针对这条评论进行回复，不要重复对方的话。"
            )

        target_desc = "回复以下评论" if parent_comment else "针对以下帖子发表一条评论"
        system_prompt = (
            f"你扮演论坛用户「{user.username}」。\n"
            f"人设: {user.persona_text}\n"
            f"\n【写作风格要求】\n{style_instruction}\n"
            f"\n【评论情绪引导】\n{attitude}\n"
            f"{time_ctx}{mood_ctx}\n"
            f"{lang_instruction}\n"
            f"{HUMANIZER_PROMPT}\n"
            f"请{target_desc}（{settings.COMMENT_MIN_LENGTH}-{settings.COMMENT_MAX_LENGTH}字），要严格符合上述写作风格。"
            "禁止笼统地夸奖或表扬，必须有自己的独立观点。"
            "只输出评论内容，不要输出其他任何内容。不要输出'回复 @xxx：'前缀。"
        )

        post_content = post.content or ""
        if image_desc:
            post_content += f"\n[图片内容: {image_desc}]"

        user_msg = f"帖子标题: {post.title}\n帖子内容: {post_content}{reply_ctx}"

        try:
            return await llm_service.chat(system_prompt, user_msg, max_tokens=512)
        except Exception as e:
            logger.error(f"生成评论失败: {e}")
            return None

    async def _generate_post(
        self,
        db: AsyncSession,
        user: User,
        announcements: List[Announcement],
        daily_topic: Optional[DailyTopic],
    ) -> Optional[Post]:
        time_ctx = _time_period_context() if settings.DAY_NIGHT_ENABLED else ""
        mood_ctx = _mood_context(user.mood) if settings.MOOD_ENABLED else ""

        announcement_ctx = ""
        if announcements:
            ann = random.choice(announcements)
            # 参与概率取决于奖励积分：0积分→5%，满积分→50%
            max_rw = max(settings.ANNOUNCEMENT_MAX_REWARD, 1)
            ratio = min(ann.reward_credits / max_rw, 1.0)
            participation = settings.ANNOUNCEMENT_MIN_PARTICIPATION + ratio * (
                settings.ANNOUNCEMENT_MAX_PARTICIPATION - settings.ANNOUNCEMENT_MIN_PARTICIPATION
            )
            if random.random() < participation:
                reward_hint = f"（参与可获得 {ann.reward_credits} 积分）" if ann.reward_credits > 0 else ""
                announcement_ctx = f"\n当前有公告活动：「{ann.title}」- {ann.content}{reward_hint}。请围绕此活动发帖。"

        topic_ctx = ""
        if daily_topic and random.random() < settings.DAILY_TOPIC_PARTICIPATION_RATE:
            topic_ctx = (
                f"\n今日话题：「{daily_topic.title}」{daily_topic.description or ''}。"
                f"你可以围绕此话题发帖，在正文中自然地带上 #{daily_topic.title} 标签即可，标题不需要直接引用话题。"
            )

        lang_instruction = ""
        if user.language == "en":
            lang_instruction = "Please write the post in English."

        is_poll = random.random() < settings.POLL_POST_PROBABILITY
        is_rumor = settings.RUMOR_ENABLED and "阴谋论" in str(user.interests_tags) and random.random() < 0.1

        poll_instruction = ""
        if is_poll:
            poll_instruction = (
                '\n这是一个投票帖。请额外生成 "poll_options" 字段，包含 2-4 个投票选项（字符串数组）。'
            )

        style_instruction = _get_style_instruction(user.expression_style)

        system_prompt = (
            f"你扮演论坛用户「{user.username}」。\n"
            f"人设: {user.persona_text}\n"
            f"\n【写作风格要求】\n{style_instruction}\n"
            f"{time_ctx}{mood_ctx}{announcement_ctx}{topic_ctx}\n"
            f"{lang_instruction}\n"
            f"{HUMANIZER_PROMPT}\n"
            "请发表一篇新帖子，正文内容必须严格符合上述写作风格。以 JSON 格式输出：\n"
            '{"title": "帖子标题", "content": "帖子正文(' + str(settings.POST_MIN_LENGTH) + '-' + str(settings.POST_MAX_LENGTH) + '字，分3-5个自然段，段落之间用\\n\\n换行)", '
            '"summary": "一句话摘要(不超过50字)", '
            '"tags": ["标签1", "标签2"]'
            f'{poll_instruction}'
            "}\n"
            "只输出 JSON，不要包含 markdown 代码块标记。"
        )

        user_msg = "请根据你的人设和兴趣，发表一篇你想写的帖子。"

        try:
            raw = await llm_service.chat(system_prompt, user_msg, max_tokens=1024)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()

            data = self._safe_parse_json(raw)
            if not data or "title" not in data:
                logger.error(f"生成帖子失败: JSON 缺少 title | raw={raw[:200]}")
                return None
        except Exception as e:
            logger.error(f"生成帖子失败: {e}")
            return None

        post = Post(
            author_id=user.id,
            title=data.get("title", "无标题"),
            content=data.get("content", ""),
            summary=data.get("summary", ""),
            is_rumor=is_rumor,
            is_poll=is_poll,
        )
        db.add(post)
        await db.flush()

        tag_names = data.get("tags", [])
        for tag_name in tag_names[:3]:
            tag_name = tag_name.strip()
            if not tag_name:
                continue
            existing_tag = (await db.execute(
                select(Tag).where(Tag.name == tag_name)
            )).scalar_one_or_none()
            if not existing_tag:
                existing_tag = Tag(name=tag_name)
                db.add(existing_tag)
                await db.flush()
            db.add(PostTag(post_id=post.id, tag_id=existing_tag.id))

        if is_rumor:
            rumor_tag = (await db.execute(
                select(Tag).where(Tag.name == "未证实")
            )).scalar_one_or_none()
            if not rumor_tag:
                rumor_tag = Tag(name="未证实")
                db.add(rumor_tag)
                await db.flush()
            db.add(PostTag(post_id=post.id, tag_id=rumor_tag.id))

        if is_poll and "poll_options" in data:
            poll = Poll(post_id=post.id, options=data["poll_options"][:settings.POLL_MAX_OPTIONS])
            db.add(poll)

        try:
            embed_text = f"{post.title} {post.summary or ''}"
            embedding = await embedding_service.embed(embed_text)
            post.content_embedding = embedding
        except Exception as e:
            logger.error(f"帖子 embedding 失败: {e}")

        if random.random() < settings.POST_IMAGE_PROBABILITY:
            try:
                img_url = await image_service.generate_post_image(
                    post.title, post.summary or ""
                )
                post.image_url = img_url
            except Exception as e:
                logger.error(f"帖子配图生成失败: {e}")

        return post

    async def _do_repost(self, db: AsyncSession, user: User, original: Post):
        repost = Post(
            author_id=user.id,
            title=f"转发: {original.title}",
            content=f"【转发自 @{original.author.username if original.author else original.author_id}(uid:{original.author_id})】{original.summary or original.title}",
            summary=original.summary,
            is_repost=True,
            repost_of=original.id,
            content_embedding=original.content_embedding,
        )
        db.add(repost)

    async def _maybe_vote_poll(self, db: AsyncSession, user: User, post: Post):
        poll = (await db.execute(
            select(Poll).where(Poll.post_id == post.id)
        )).scalar_one_or_none()
        if not poll:
            return

        existing_vote = (await db.execute(
            select(PollVote).where(PollVote.poll_id == poll.id, PollVote.user_id == user.id)
        )).scalar_one_or_none()
        if existing_vote:
            return

        if poll.options:
            option_idx = random.randint(0, len(poll.options) - 1)
            vote = PollVote(poll_id=poll.id, user_id=user.id, option_index=option_idx)
            db.add(vote)

    async def _track_interaction(self, db: AsyncSession, user_a_id: int, user_b_id: int):
        if user_a_id == user_b_id:
            return

        a, b = min(user_a_id, user_b_id), max(user_a_id, user_b_id)
        interaction = (await db.execute(
            select(UserInteraction).where(
                UserInteraction.user_a_id == a, UserInteraction.user_b_id == b
            )
        )).scalar_one_or_none()

        if interaction:
            interaction.count += 1
            interaction.last_interaction_at = datetime.now(timezone.utc)
        else:
            interaction = UserInteraction(
                user_a_id=a, user_b_id=b, count=1
            )
            db.add(interaction)
            await db.flush()

        if interaction.count >= settings.AUTO_FOLLOW_INTERACTION_THRESHOLD:
            for fa, fb in [(user_a_id, user_b_id), (user_b_id, user_a_id)]:
                existing = (await db.execute(
                    select(UserFollow).where(
                        UserFollow.follower_id == fa, UserFollow.following_id == fb
                    )
                )).scalar_one_or_none()
                if not existing:
                    db.add(UserFollow(follower_id=fa, following_id=fb))


behavior_engine = BehaviorEngine()
