import io
import os
import uuid
import random
import logging
import asyncio

import httpx
import aiofiles
from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)


class ImageService:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=120.0)
        self._uapi_client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=10.0),
            follow_redirects=True,
        )
        self._semaphore = asyncio.Semaphore(2)

    @property
    def _uapi_headers(self) -> dict:
        return {"Authorization": f"Bearer {settings.UAPI_KEY}"}

    # ==================== 通用工具 ====================

    def _compress_image(self, data: bytes, max_size: int = None, quality: int = None) -> bytes:
        """压缩图片到指定尺寸和质量，返回 JPEG bytes"""
        max_size = max_size or settings.AVATAR_MAX_SIZE
        quality = quality or settings.AVATAR_QUALITY
        try:
            img = Image.open(io.BytesIO(data))
            img = img.convert("RGB")
            # 等比缩放到 max_size x max_size
            img.thumbnail((max_size, max_size), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            compressed = buf.getvalue()
            logger.debug(f"图片压缩: {len(data)//1024}KB → {len(compressed)//1024}KB ({img.size[0]}x{img.size[1]})")
            return compressed
        except Exception as e:
            logger.warning(f"图片压缩失败，使用原图: {e}")
            return data

    async def download_and_save(self, image_url: str, save_dir: str, prefix: str = "", compress: bool = False) -> str:
        os.makedirs(save_dir, exist_ok=True)
        ext = ".jpg" if compress else ".png"
        filename = f"{prefix}{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(save_dir, filename)
        try:
            response = await self.client.get(image_url)
            response.raise_for_status()
            data = response.content
            if compress:
                data = self._compress_image(data)
            async with aiofiles.open(filepath, "wb") as f:
                await f.write(data)
            return filename
        except Exception as e:
            logger.error(f"图片下载保存失败: {e}")
            raise

    # ==================== 模型生图 ====================

    async def generate_image(self, prompt: str, max_retries: int = 3) -> str:
        logger.info(f"生图请求 | 提示: {prompt[:80]}...")
        async with self._semaphore:
            for attempt in range(max_retries):
                try:
                    response = await self.client.post(
                        f"{settings.IMAGE_GEN_API_BASE_URL}/images/generations",
                        headers={"Authorization": f"Bearer {settings.IMAGE_GEN_API_KEY}"},
                        json={
                            "model": settings.IMAGE_GEN_MODEL,
                            "prompt": prompt,
                            "n": 1,
                            "size": settings.IMAGE_SIZE,
                            "num_inference_steps": settings.IMAGE_INFERENCE_STEPS,
                            "guidance_scale": settings.IMAGE_GUIDANCE_SCALE,
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    image_url = data["images"][0]["url"]
                    logger.info(f"生图完成 | URL: {image_url[:80]}")
                    return image_url
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429 and attempt < max_retries - 1:
                        wait = 2 ** (attempt + 1)
                        logger.warning(f"生图限流 429，{wait}s 后重试 ({attempt+1}/{max_retries})")
                        await asyncio.sleep(wait)
                        continue
                    logger.error(f"图像生成失败: {e}")
                    raise
                except Exception as e:
                    logger.error(f"图像生成失败: {e}")
                    raise

    # ==================== API 随机头像 ====================

    def _pick_avatar_params(self) -> dict:
        """根据权重随机选择头像 API 参数"""
        category = random.choices(
            ["bq", "landscape", "furry"],
            weights=[0.50, 0.30, 0.20],
            k=1,
        )[0]

        params = {"category": category}

        if category == "bq":
            sub_type = random.choices(
                ["ikun", "xiongmao", "waiguoren", "maomao", "eciyuan"],
                weights=[0.35, 0.20, 0.15, 0.15, 0.15],
                k=1,
            )[0]
            params["type"] = sub_type
        elif category == "furry":
            sub_type = random.choice(["z4k", "szs8k", "s4k", "4k"])
            params["type"] = sub_type

        return params

    async def _fetch_api_avatar(self) -> bytes:
        """从 UapiPro 获取随机图片并返回原始 bytes"""
        params = self._pick_avatar_params()
        url = f"{settings.UAPI_BASE_URL}/random/image"
        logger.info(f"API头像请求 | category={params.get('category')} type={params.get('type', '-')}")

        response = await self._uapi_client.get(
            url, params=params, headers=self._uapi_headers,
        )
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "image" not in content_type and len(response.content) < 1000:
            raise ValueError(f"API返回非图片: content-type={content_type}, len={len(response.content)}")

        return response.content

    async def generate_avatar_api(self) -> str:
        """使用 UapiPro API 生成头像（下载→压缩→保存）"""
        os.makedirs(settings.AVATAR_DIR, exist_ok=True)

        data = await self._fetch_api_avatar()
        compressed = self._compress_image(data)

        filename = f"avatar_{uuid.uuid4().hex}.jpg"
        filepath = os.path.join(settings.AVATAR_DIR, filename)
        async with aiofiles.open(filepath, "wb") as f:
            await f.write(compressed)

        logger.info(f"API头像保存: {filename} ({len(compressed)//1024}KB)")
        return f"/static/avatars/{filename}"

    # ==================== 模型生成头像 ====================

    async def generate_avatar_model(self, persona: dict) -> str:
        """使用生图模型生成头像"""
        logger.info(f"模型头像生成 | 用户: {persona.get('occupation', '?')}")

        avatar_type = random.choices(
            ["person", "landscape", "animal", "object", "abstract"],
            weights=[0.45, 0.15, 0.15, 0.15, 0.10],
            k=1,
        )[0]

        if avatar_type == "person":
            traits = []
            if persona.get("age"):
                traits.append(f"{persona['age']}岁")
            if persona.get("occupation"):
                traits.append(persona["occupation"])
            if persona.get("interests_tags"):
                interests = persona["interests_tags"][:2] if isinstance(persona["interests_tags"], list) else []
                traits.extend(interests)
            trait_str = "、".join(traits)
            prompt = (
                f"一个{trait_str}的人物头像，真实摄影风格，自然光线，"
                "浅色纯净背景，面部清晰自然，专业人像摄影，高清质感，"
                "不要动漫风格，不要卡通，不要插画"
            )
        elif avatar_type == "landscape":
            scenes = [
                "壮观的山脉日落风景", "宁静的湖泊倒影", "樱花盛开的小路",
                "星空银河", "海边悬崖灯塔", "秋天红叶森林",
                "雪山草甸", "热带海滩棕榈树", "城市夜景天际线",
                "薰衣草花田", "雾气缭绕的竹林", "沙漠中的绿洲",
            ]
            prompt = f"{random.choice(scenes)}，真实摄影风格，高清质感，适合做头像的构图"
        elif avatar_type == "animal":
            animals = [
                "一只可爱的橘猫", "一只优雅的暹罗猫", "一只微笑的柴犬",
                "一只呆萌的柯基", "一只威严的老鹰", "一只慵懒的英短猫",
                "一只调皮的哈士奇", "一只酷酷的黑猫", "一只正在打哈欠的猫",
                "一只蹲坐的兔子", "一只树上的猫头鹰", "一只游泳的鸭子",
            ]
            prompt = f"{random.choice(animals)}，真实摄影风格，浅色背景，高清质感，适合做头像"
        elif avatar_type == "object":
            objects = [
                "一辆红色复古跑车", "一杯精致的拿铁拉花咖啡", "一把电吉他",
                "一个复古胶片相机", "一盆多肉植物", "一双AJ球鞋",
                "一个精致的机械手表", "一架钢琴键盘特写", "一个游戏手柄",
                "一辆摩托车侧面", "一把日本武士刀", "一个地球仪",
            ]
            prompt = f"{random.choice(objects)}，产品摄影风格，简洁背景，高清质感，适合做头像"
        else:
            styles = [
                "抽象几何图案，渐变色彩", "赛博朋克风格数字艺术",
                "水彩晕染效果", "极简线条艺术", "像素风格游戏角色",
                "漩涡状星云图案", "低多边形风格3D艺术",
                "日式浮世绘风格图案", "蒸汽波美学图案",
            ]
            prompt = f"{random.choice(styles)}，高清质感，适合做社交媒体头像"

        remote_url = await self.generate_image(prompt)
        filename = await self.download_and_save(remote_url, settings.AVATAR_DIR, prefix="avatar_", compress=True)
        return f"/static/avatars/{filename}"

    # ==================== 统一入口 ====================

    async def generate_avatar(self, persona: dict) -> str:
        """根据配置选择 API 或模型生成头像"""
        if settings.AVATAR_MODE == "api":
            try:
                return await self.generate_avatar_api()
            except Exception as e:
                logger.warning(f"API头像失败，回退到模型生成: {e}")
                return await self.generate_avatar_model(persona)
        else:
            return await self.generate_avatar_model(persona)

    async def generate_post_image(self, title: str, summary: str = "") -> str:
        logger.info(f"帖子配图 | 标题: {title[:50]}")
        context = title
        if summary:
            context += f"，{summary}"
        prompt = (
            f"根据以下主题生成一张配图：{context}。"
            "真实摄影风格，高清质感，自然色调，专业新闻配图风格，"
            "不要动漫风格，不要卡通，不要插画"
        )

        remote_url = await self.generate_image(prompt)
        filename = await self.download_and_save(remote_url, settings.POST_IMAGE_DIR, prefix="post_")
        return f"/static/post_images/{filename}"

    async def close(self):
        await self.client.aclose()
        await self._uapi_client.aclose()


image_service = ImageService()
