"""LLM 服务：OpenAI 兼容协议（默认 DeepSeek），未配置 API Key 时返回 None 由上层降级。

提供两条调用通道：
1) LLMService：直接 httpx 调 /chat/completions（旧 handler 仍用，含 JSON mode）
2) get_chat_model()：返回 LangChain ChatOpenAI 实例，支持 bind_tools() 原生 function calling
"""
import asyncio
import json
import logging

import httpx

from ..config import settings

logger = logging.getLogger("zhinan.llm")


def get_chat_model(temperature: float = 0.3, model: str | None = None,
                   api_key: str | None = None, api_base: str | None = None):
    """返回 LangChain ChatOpenAI 实例（指向 DeepSeek，兼容 OpenAI function calling 协议）。

    用于 agent/graph.py 的 llm_decision 节点：bind_tools 后让 LLM 自动决定调用哪个工具。
    支持 per-user 覆盖：若传入 api_key/api_base 则使用用户自定义配置，否则用系统默认。
    未配置 API Key 时抛 RuntimeError，由调用方降级到旧正则分支。
    """
    use_key = api_key or settings.llm_api_key
    use_base = api_base or settings.llm_api_base
    use_model = model or settings.llm_model
    if not use_key:
        raise RuntimeError("LLM 未启用（LLM_API_KEY 为空），无法使用 LangChain Tool Calling")
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=use_model,
        api_key=use_key,
        base_url=use_base,
        temperature=temperature,
        max_tokens=settings.llm_max_tokens,
    )

SYSTEM_PROMPT = (
    "你是「知南·Echo」，一名懂学习、知节奏的大学生学业助手智能体。"
    "你说话亲切、简洁、有条理，善用简短的分点表达，不啰嗦。"
    "当用户的请求与学习管理（资料、DDL、复习）无关时，礼貌地把话题引回学习。"
)

JSON_INSTRUCTION = "请只输出一个合法的 JSON 对象，不要输出任何其他文字、注释或代码块标记。"


class LLMService:
    @property
    def enabled(self) -> bool:
        return settings.llm_enabled

    async def chat(
        self,
        messages: list[dict],
        json_mode: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> str | None:
        """调用 chat/completions；失败或未配置时返回 None。

        速率限制(429)采用指数退避重试；主模型彻底失败时自动降级到轻量模型。
        支持 per-user 覆盖：传入 api_key/api_base 则用用户自定义配置。
        """
        use_key = api_key or settings.llm_api_key
        use_base = api_base or settings.llm_api_base
        if not use_key:
            return None
        base_payload = {
            "messages": messages,
            "temperature": settings.llm_temperature if temperature is None else temperature,
            "max_tokens": settings.llm_max_tokens if max_tokens is None else max_tokens,
        }
        if json_mode:
            base_payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {use_key}"}

        async def _call(model_name: str) -> str | None:
            payload = {**base_payload, "model": model_name}
            last_error = ""
            for backoff in (0, 2, 4, 8):     # 429 限流指数退避
                if backoff:
                    await asyncio.sleep(backoff)
                try:
                    async with httpx.AsyncClient(timeout=120) as client:
                        resp = await client.post(
                            f"{use_base.rstrip('/')}/chat/completions",
                            json=payload, headers=headers,
                        )
                        if resp.status_code == 429:
                            last_error = "rate-limited"
                            continue
                        resp.raise_for_status()
                        return resp.json()["choices"][0]["message"]["content"]
                except Exception as exc:  # noqa: BLE001
                    last_error = str(exc)[:80]
                    logger.warning("LLM 调用失败(%s): %s", model_name, last_error)
            return None

        primary = model or settings.llm_model
        result = await _call(primary)
        if result is not None:
            return result
        # 主模型不可用 → 降级轻量模型（如 glm-4.7 限流时退到 glm-4-flash）
        if primary != settings.llm_fast_model:
            logger.warning("主模型 %s 不可用，降级到 %s", primary, settings.llm_fast_model)
            return await _call(settings.llm_fast_model)
        return None

    async def chat_json(self, user_prompt: str, system: str | None = None,
                        model: str | None = None) -> dict | None:
        """要求模型输出 JSON 并解析；失败返回 None。"""
        content = await self.chat(
            [{"role": "system", "content": (system or SYSTEM_PROMPT) + "\n" + JSON_INSTRUCTION},
             {"role": "user", "content": user_prompt}],
            json_mode=True, temperature=0.1, model=model,
        )
        if content is None:
            return None
        return self._loads(content)

    @staticmethod
    def _loads(content: str) -> dict | None:
        content = content.strip()
        if content.startswith("```"):
            content = content.strip("`")
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start, end = content.find("{"), content.rfind("}")
            if 0 <= start < end:
                try:
                    return json.loads(content[start:end + 1])
                except json.JSONDecodeError:
                    return None
        return None


llm = LLMService()
