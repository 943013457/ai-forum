import os
import logging
from datetime import datetime
from typing import List, Dict, Optional

import httpx
import aiofiles

from app.config import settings

logger = logging.getLogger(__name__)


class NewsService:
    """通过 UapiPro 获取新闻热榜、全文内容及每日新闻摘要图"""

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
        )
        self._last_fetch_hour: Optional[int] = None
        self._startup_done: bool = False

    @property
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {settings.UAPI_KEY}"}

    # ==================== 定时判断 ====================

    def should_fetch_now(self, force: bool = False) -> bool:
        """判断当前时刻是否应该获取新闻。force=True 用于启动时强制获取"""
        if force:
            return True

        try:
            schedule = [int(h.strip()) for h in settings.NEWS_SCHEDULE_HOURS.split(",")]
        except ValueError:
            schedule = [8, 12, 15, 18, 20, 0]

        now = datetime.now()
        current_hour = now.hour

        if current_hour not in schedule:
            return False
        if self._last_fetch_hour == current_hour:
            return False
        return True

    def mark_fetched(self):
        """标记当前小时已获取过"""
        self._last_fetch_hour = datetime.now().hour

    # ==================== 知乎热榜 ====================

    async def get_zhihu_hotboard(self, limit: int = None) -> List[Dict]:
        """获取知乎热榜前 N 条"""
        limit = limit or settings.NEWS_TOP_N
        url = f"{settings.UAPI_BASE_URL}/misc/hotboard"

        try:
            response = await self.client.get(
                url, params={"type": "zhihu"}, headers=self._headers,
            )
            response.raise_for_status()
            data = response.json()

            items = data.get("list", [])[:limit]
            result = []
            for item in items:
                title = (item.get("title") or "").strip()
                if not title:
                    continue
                result.append({
                    "title": title,
                    "url": item.get("url", ""),
                    "hot_value": item.get("hot_value", ""),
                    "index": item.get("index", 0),
                })

            logger.info(f"知乎热榜获取成功 | 数量={len(result)}")
            return result

        except Exception as e:
            logger.warning(f"知乎热榜获取失败: {e}")
            return []

    # ==================== 智能搜索全文 ====================

    async def search_full_content(self, query: str) -> Optional[Dict]:
        """使用聚合搜索获取新闻全文"""
        url = f"{settings.UAPI_BASE_URL}/search/aggregate"

        try:
            response = await self.client.post(
                url,
                headers={**self._headers, "Content-Type": "application/json"},
                json={"query": query, "fetch_full": True},
                timeout=httpx.Timeout(60.0, connect=15.0),
            )
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            if not results:
                logger.info(f"搜索无结果: {query[:30]}")
                return None

            # 优先选择有 full_content 的结果
            for r in results:
                full = r.get("full_content", "")
                if full and len(full) > 100:
                    return {
                        "title": r.get("title", query),
                        "url": r.get("url", ""),
                        "domain": r.get("domain", ""),
                        "snippet": r.get("snippet", ""),
                        "full_content": full,
                        "publish_time": r.get("publish_time", ""),
                    }

            # 回退：用 snippet 最长的
            best = max(results, key=lambda x: len(x.get("snippet", "")))
            return {
                "title": best.get("title", query),
                "url": best.get("url", ""),
                "domain": best.get("domain", ""),
                "snippet": best.get("snippet", ""),
                "full_content": best.get("snippet", ""),
                "publish_time": best.get("publish_time", ""),
            }

        except Exception as e:
            logger.warning(f"搜索全文失败 | query={query[:30]}: {e}")
            return None

    # ==================== 完整新闻获取流程 ====================

    async def fetch_news_with_content(self, limit: int = None, skip_titles: set = None) -> List[Dict]:
        """知乎热榜 → 逐条搜索全文 → 返回带全文的新闻列表
        skip_titles: 已存在的标题集合，跳过这些标题的全文搜索"""
        hotboard = await self.get_zhihu_hotboard(limit)
        if not hotboard:
            return []

        skip = skip_titles or set()
        news_with_content = []
        for item in hotboard:
            title = item["title"]
            if title in skip:
                logger.info(f"跳过重复新闻: {title[:40]}")
                continue
            detail = await self.search_full_content(title)
            if detail:
                news_with_content.append({
                    "title": title,
                    "url": detail.get("url") or item.get("url", ""),
                    "domain": detail.get("domain", ""),
                    "hot_value": item.get("hot_value", ""),
                    "full_content": detail.get("full_content", ""),
                    "publish_time": detail.get("publish_time", ""),
                })
                logger.info(f"新闻全文获取成功: {title[:40]}...")
            else:
                # 无全文，仅用标题发帖
                news_with_content.append({
                    "title": title,
                    "url": item.get("url", ""),
                    "domain": "zhihu.com",
                    "hot_value": item.get("hot_value", ""),
                    "full_content": "",
                    "publish_time": "",
                })
                logger.info(f"新闻全文缺失，仅标题: {title[:40]}...")

        return news_with_content

    # ==================== 每日新闻摘要图 ====================

    async def fetch_news_image(self) -> Optional[str]:
        """获取每日新闻摘要图片，保存后返回相对 URL"""
        url = f"{settings.UAPI_BASE_URL}/daily/news-image"
        os.makedirs(settings.NEWS_IMAGE_DIR, exist_ok=True)

        try:
            response = await self.client.get(
                url, headers=self._headers,
                timeout=httpx.Timeout(30.0, connect=15.0),
            )
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "image" not in content_type:
                logger.warning(f"新闻图API返回非图片: {content_type}")
                return None

            # 按日期命名，便于缓存
            date_str = datetime.now().strftime("%Y%m%d")
            hour_str = datetime.now().strftime("%H")
            filename = f"news_{date_str}_{hour_str}.jpg"
            filepath = os.path.join(settings.NEWS_IMAGE_DIR, filename)

            async with aiofiles.open(filepath, "wb") as f:
                await f.write(response.content)

            logger.info(f"新闻摘要图保存: {filename} ({len(response.content)//1024}KB)")
            return f"/static/news_images/{filename}"

        except Exception as e:
            logger.warning(f"新闻摘要图获取失败: {e}")
            return None

    async def close(self):
        await self.client.aclose()


news_service = NewsService()
