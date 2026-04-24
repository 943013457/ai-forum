import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class VisionService:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=60.0)

    async def describe_image(self, image_url: str) -> str:
        logger.info(f"视觉识别 | 图片: {image_url[:80]}")
        try:
            response = await self.client.post(
                f"{settings.VISION_API_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {settings.VISION_API_KEY}"},
                json={
                    "model": settings.VISION_MODEL,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": image_url},
                                },
                                {
                                    "type": "text",
                                    "text": "请用中文描述这张图片的内容，包括主要物体、场景、颜色和氛围。不超过 200 字。",
                                },
                            ],
                        }
                    ],
                    "max_tokens": 512,
                },
            )
            response.raise_for_status()
            data = response.json()
            desc = data["choices"][0]["message"]["content"]
            logger.info(f"视觉识别完成 | 描述: {desc[:60].replace(chr(10), ' ')}...")
            return desc
        except Exception as e:
            logger.error(f"视觉识别失败: {type(e).__name__}: {e}")
            raise

    async def close(self):
        await self.client.aclose()


vision_service = VisionService()
