import logging
from typing import List

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=60.0)

    async def embed(self, text: str) -> List[float]:
        logger.info(f"Embedding 单条 | 文本: {text[:60].replace(chr(10), ' ')}...")
        try:
            response = await self.client.post(
                f"{settings.EMBEDDING_API_BASE_URL}/embeddings",
                headers={"Authorization": f"Bearer {settings.EMBEDDING_API_KEY}"},
                json={
                    "model": settings.EMBEDDING_MODEL,
                    "input": text,
                    "encoding_format": "float",
                },
            )
            response.raise_for_status()
            data = response.json()
            embedding = data["data"][0]["embedding"]
            logger.info(f"Embedding 完成 | 维度: {len(embedding)}")
            return embedding
        except Exception as e:
            logger.error(f"Embedding 调用失败: {type(e).__name__}: {e}")
            raise

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        logger.info(f"Embedding 批量 | 数量: {len(texts)}")
        try:
            response = await self.client.post(
                f"{settings.EMBEDDING_API_BASE_URL}/embeddings",
                headers={"Authorization": f"Bearer {settings.EMBEDDING_API_KEY}"},
                json={
                    "model": settings.EMBEDDING_MODEL,
                    "input": texts,
                    "encoding_format": "float",
                },
            )
            response.raise_for_status()
            data = response.json()
            sorted_data = sorted(data["data"], key=lambda x: x["index"])
            return [d["embedding"] for d in sorted_data]
        except Exception as e:
            logger.error(f"Embedding 批量调用失败: {e}")
            raise

    async def close(self):
        await self.client.aclose()


embedding_service = EmbeddingService()
