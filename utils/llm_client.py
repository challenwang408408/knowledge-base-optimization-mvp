from __future__ import annotations

import time
import logging
from typing import Any

from openai import OpenAI, APIError, APITimeoutError, RateLimitError

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF = [1, 2, 4]
DEFAULT_TIMEOUT = 60


class LLMClient:
    """OpenAI 兼容 LLM 客户端，支持重试与超时。"""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.model = model
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=DEFAULT_TIMEOUT,
        )

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """调用 chat completion 接口，自带重试。

        Returns:
            模型返回的文本内容。
        Raises:
            RuntimeError: 重试耗尽后仍失败。
        """
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_completion_tokens=max_tokens,
                )
                return resp.choices[0].message.content or ""
            except (APITimeoutError, RateLimitError) as e:
                last_error = e
                wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                logger.warning(
                    "LLM 调用失败 (尝试 %d/%d)：%s，%ds 后重试",
                    attempt + 1, MAX_RETRIES, e, wait,
                )
                time.sleep(wait)
            except APIError as e:
                raise RuntimeError(f"LLM API 错误：{e}") from e
            except Exception as e:
                raise RuntimeError(f"LLM 调用异常：{e}") from e

        raise RuntimeError(
            f"LLM 调用在 {MAX_RETRIES} 次重试后仍失败：{last_error}"
        )
