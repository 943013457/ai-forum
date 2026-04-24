import asyncio
import time
import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class TokenBucketRateLimiter:
    def __init__(self, max_per_hour: int):
        self.max_per_hour = max_per_hour
        self.tokens = float(max_per_hour)
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(
                self.max_per_hour,
                self.tokens + elapsed * (self.max_per_hour / 3600.0),
            )
            self.last_refill = now
            if self.tokens < 1.0:
                wait_time = (1.0 - self.tokens) / (self.max_per_hour / 3600.0)
                logger.warning(f"LLM 速率限制：等待 {wait_time:.1f} 秒")
                await asyncio.sleep(wait_time)
                self.tokens = 0.0
            else:
                self.tokens -= 1.0


class LLMService:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=120.0)
        self.rate_limiter = TokenBucketRateLimiter(settings.MAX_LLM_CALLS_PER_HOUR)
        self._call_count = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    def reset_call_count(self):
        self._call_count = 0

    async def chat(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.8,
        max_tokens: int = 1024,
        enable_thinking: bool = True,
    ) -> str:
        await self.rate_limiter.acquire()
        self._call_count += 1
        prompt_preview = user_message[:80].replace('\n', ' ')
        logger.info(f"LLM 调用 #{self._call_count} | 提示: {prompt_preview}...")
        try:
            import time as _time
            _start = _time.time()
            response = await self.client.post(
                f"{settings.LLM_API_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
                json={
                    "model": settings.LLM_MODEL_NAME,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    **({
                        "enable_thinking": False,
                        "thinking": {"type": "disabled"},
                    } if not enable_thinking else {}),
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            elapsed = ((_time.time() - _start) * 1000)
            usage = data.get("usage", {})
            logger.info(
                f"LLM 响应 #{self._call_count} | {elapsed:.0f}ms | "
                f"tokens: {usage.get('total_tokens', '?')} | "
                f"回复: {content[:60].replace(chr(10), ' ')}..."
            )
            return content
        except httpx.HTTPStatusError as e:
            logger.error(f"LLM HTTP 错误: {e.response.status_code} {e.response.text[:200]}")
            raise
        except Exception as e:
            logger.error(f"LLM 调用失败: {type(e).__name__}: {e}")
            raise

    async def chat_json(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        system_prompt_json = system_prompt + "\n\n请严格以 JSON 格式输出，不要包含 markdown 代码块标记。"
        return await self.chat(system_prompt_json, user_message, temperature, max_tokens)

    async def close(self):
        await self.client.aclose()


llm_service = LLMService()
