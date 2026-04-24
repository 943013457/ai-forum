import logging

from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


async def generate_summary(title: str, content: str) -> str:
    system_prompt = "请用一句话（不超过50字）总结以下帖子的主题。只输出摘要文本。"
    user_msg = f"标题: {title}\n内容: {content}"
    try:
        return await llm_service.chat(system_prompt, user_msg, max_tokens=128)
    except Exception as e:
        logger.error(f"生成摘要失败: {e}")
        return title[:50]
