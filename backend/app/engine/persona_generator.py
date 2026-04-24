import json
import random
import logging
from typing import List, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.config import settings
from app.models import User
from app.services.llm_service import llm_service
from app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)

# ==================== 仅作为 LLM 失败时的 fallback ====================
FALLBACK_OCCUPATIONS = [
    "程序员", "产品经理", "设计师", "教师", "医生", "律师", "记者",
    "厨师", "摄影师", "音乐人", "作家", "学生", "自由职业者",
    "外卖骑手", "会计", "护士", "健身教练", "插画师", "导演",
]
FALLBACK_EDUCATIONS = ["高中", "大专", "本科", "硕士", "博士", "初中"]
FALLBACK_STYLES = [
    "幽默搞笑", "严肃理性", "文艺感性", "毒舌犀利", "温暖鸡汤",
    "阴阳怪气", "极简冷淡", "表情包达人", "学术严谨", "网络冲浪高手",
]
FALLBACK_INTERESTS = [
    "编程", "游戏", "动漫", "美食", "旅行", "摄影", "音乐", "电影",
    "读书", "健身", "篮球", "投资理财", "心理学", "历史", "哲学",
    "政治", "科技", "AI", "区块链", "宠物", "穿搭", "化妆",
    "汽车", "数码", "追星", "二次元", "阴谋论", "天文", "钓鱼", "咖啡",
]
PERSONALITY_TRAITS = ["开放性", "尽责性", "外向性", "宜人性", "神经质"]

LLM_PERSONA_BATCH = 10  # 每次 LLM 调用生成的人设数量


class PersonaGenerator:

    async def _generate_personas_llm(self, count: int) -> List[Dict]:
        """LLM 批量生成完整人设"""
        prompt = (
            "你是一个虚拟论坛用户生成器。请生成一批多样化的论坛用户角色。\n"
            "每个角色包含以下字段：\n"
            "- username: 互联网网名（2-10字，模拟真实网民风格：中二/文艺/搞笑/自嘲/古风/简约/英文混搭/谐音梗/带数字等）\n"
            f"- age: 年龄（{settings.PERSONA_MIN_AGE}-{settings.PERSONA_MAX_AGE}岁之间）\n"
            "- occupation: 职业（真实多样，不要重复）\n"
            "- education: 学历（初中/高中/大专/本科/硕士/博士）\n"
            "- interests: 兴趣爱好数组（2-5个，具体且多样化）\n"
            "- expression_style: 说话风格（如：幽默搞笑/严肃理性/文艺感性/毒舌犀利/温暖鸡汤/阴阳怪气/极简冷淡/表情包达人/学术严谨/网络冲浪高手/口嗨王者/佛系淡定/暴躁老哥 等）\n"
            "- personality: Big Five 性格值对象 {开放性, 尽责性, 外向性, 宜人性, 神经质}，每个 0.1-1.0\n"
            "- bio: 用第一人称写一段人设描述（50-100字），包括性格特点、口头禅、看待世界的方式\n\n"
            "要求：\n"
            "- 角色之间差异要大，覆盖不同年龄段、职业、性格\n"
            "- 网名风格要丰富多样，像真实论坛用户\n"
            "- 兴趣不要千篇一律\n"
            "- 只输出 JSON 数组，不要包含 markdown 代码块标记\n"
        )
        try:
            raw = await llm_service.chat(
                prompt,
                f"请生成 {count} 个完全不同的论坛用户角色。输出 JSON 数组。",
                max_tokens=4096,
                enable_thinking=False,
            )
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()

            personas = json.loads(raw)
            if not isinstance(personas, list):
                return []

            result = []
            for p in personas:
                if not isinstance(p, dict) or "username" not in p:
                    continue
                # 标准化字段
                personality = p.get("personality", {})
                if isinstance(personality, dict):
                    personality = {
                        k: max(0.1, min(1.0, float(v)))
                        for k, v in personality.items()
                    }
                else:
                    personality = {t: round(random.uniform(0.1, 1.0), 2) for t in PERSONALITY_TRAITS}

                interests = p.get("interests", [])
                if not isinstance(interests, list) or len(interests) == 0:
                    interests = random.sample(FALLBACK_INTERESTS, 3)

                result.append({
                    "username": str(p["username"]).strip()[:15],
                    "age": int(p.get("age", random.randint(18, 55))),
                    "occupation": str(p.get("occupation", random.choice(FALLBACK_OCCUPATIONS))),
                    "education": str(p.get("education", random.choice(FALLBACK_EDUCATIONS))),
                    "personality_json": personality,
                    "interests_tags": [str(i) for i in interests[:5]],
                    "expression_style": str(p.get("expression_style", random.choice(FALLBACK_STYLES))),
                    "persona_text": str(p.get("bio", "")),
                })
            logger.info(f"LLM 生成了 {len(result)} 个完整人设")
            return result
        except Exception as e:
            logger.warning(f"LLM 生成人设失败: {e}")
            return []

    def _random_persona_fallback(self) -> Dict:
        """随机生成人设（LLM 失败时的 fallback）"""
        age = random.randint(settings.PERSONA_MIN_AGE, settings.PERSONA_MAX_AGE)
        occupation = random.choice(FALLBACK_OCCUPATIONS)
        education = random.choice(FALLBACK_EDUCATIONS)
        interests = random.sample(FALLBACK_INTERESTS, k=random.randint(2, 5))
        style = random.choice(FALLBACK_STYLES)
        personality = {t: round(random.uniform(0.1, 1.0), 2) for t in PERSONALITY_TRAITS}
        username = f"用户{random.randint(10000, 99999)}"
        persona_text = (
            f"我是{username}，{age}岁，{occupation}，学历{education}。"
            f"我对{'、'.join(interests)}感兴趣。"
            f"我的表达风格是{style}。"
        )
        return {
            "username": username,
            "age": age,
            "occupation": occupation,
            "education": education,
            "personality_json": personality,
            "interests_tags": interests,
            "expression_style": style,
            "persona_text": persona_text,
        }

    async def _ensure_unique_name(self, db: AsyncSession, name: str, used: set) -> str:
        candidate = name
        for _ in range(10):
            if candidate not in used:
                exists = (await db.execute(
                    select(func.count(User.id)).where(User.username == candidate)
                )).scalar()
                if not exists:
                    used.add(candidate)
                    return candidate
            candidate = f"{name}{random.randint(1, 9999)}"
        fallback = f"{name}_{random.randint(10000, 99999)}"
        used.add(fallback)
        return fallback

    async def generate_batch(self, db: AsyncSession, count: int = None) -> List[User]:
        count = count or settings.PERSONA_BATCH_SIZE
        existing_count = (await db.execute(select(func.count(User.id)))).scalar() or 0
        used_names: set = set()

        # 分批调用 LLM 生成完整人设
        all_personas: List[Dict] = []
        remaining = count
        while remaining > 0:
            batch_size = min(LLM_PERSONA_BATCH, remaining)
            llm_personas = await self._generate_personas_llm(batch_size)
            all_personas.extend(llm_personas)
            remaining -= len(llm_personas) if llm_personas else batch_size
            # LLM 返回不足时用 fallback 补齐
            if len(llm_personas) < batch_size:
                for _ in range(batch_size - len(llm_personas)):
                    all_personas.append(self._random_persona_fallback())
                remaining = 0  # fallback 已补齐，不再循环

        users = []
        for persona_data in all_personas[:count]:
            # 确保网名唯一
            raw_name = persona_data["username"]
            username = await self._ensure_unique_name(db, raw_name, used_names)
            persona_data["username"] = username

            # 如果 LLM 没给 bio，自动生成
            if not persona_data.get("persona_text"):
                persona_data["persona_text"] = (
                    f"我是{username}，{persona_data['age']}岁，{persona_data['occupation']}，"
                    f"学历{persona_data['education']}。"
                    f"我对{'、'.join(persona_data['interests_tags'])}感兴趣。"
                    f"我的表达风格是{persona_data['expression_style']}。"
                )

            lang = "zh"
            if settings.MULTILANG_ENABLED and random.random() < settings.FOREIGN_USER_RATIO:
                lang = "en"

            user = User(
                username=username,
                persona_text=persona_data["persona_text"],
                age=persona_data["age"],
                occupation=persona_data["occupation"],
                education=persona_data["education"],
                personality_json=persona_data["personality_json"],
                interests_tags=persona_data["interests_tags"],
                expression_style=persona_data["expression_style"],
                language=lang,
                activity_level=random.choice(["high", "medium", "low"]),
                lifecycle_stage="newbie",
            )

            if random.random() < settings.LURKER_RATIO:
                user.expression_style = "潜水"
            elif random.random() < settings.REPOSTER_RATIO:
                user.expression_style = "转发党"

            users.append(user)

        db.add_all(users)
        await db.flush()

        # 批量生成兴趣向量
        interest_texts = [
            "、".join(u.interests_tags) + " " + u.occupation for u in users
        ]
        try:
            embeddings = await embedding_service.embed_batch(interest_texts)
            for user, emb in zip(users, embeddings):
                user.interest_embedding = emb
        except Exception as e:
            logger.error(f"批量 embedding 失败，跳过: {e}")

        await db.commit()

        if settings.ALT_ACCOUNT_RATIO > 0:
            await self._create_alt_accounts(db, users)

        logger.info(f"已生成 {len(users)} 个 AI 用户（总计: {existing_count + count}）")
        return users

    async def _create_alt_accounts(self, db: AsyncSession, main_users: List[User]):
        alt_count = int(len(main_users) * settings.ALT_ACCOUNT_RATIO)
        if alt_count == 0:
            return

        candidates = random.sample(main_users, min(alt_count, len(main_users)))
        alts = []
        for main_user in candidates:
            alt_style = random.choice(["毒舌犀利", "阴阳怪气", "极简冷淡"])
            alt = User(
                username=f"匿名_{random.randint(10000, 99999)}",
                persona_text=f"这是 {main_user.username} 的小号，表达风格更加放飞自我。",
                age=main_user.age,
                occupation=main_user.occupation,
                education=main_user.education,
                personality_json=main_user.personality_json,
                interests_tags=main_user.interests_tags,
                expression_style=alt_style,
                language=main_user.language,
                activity_level="low",
                lifecycle_stage="newbie",
                alt_of=main_user.id,
                interest_embedding=main_user.interest_embedding,
            )
            alts.append(alt)

        db.add_all(alts)
        await db.commit()
        logger.info(f"已为 {len(alts)} 个用户创建小号")


persona_generator = PersonaGenerator()
