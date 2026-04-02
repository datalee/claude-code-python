"""API Service - Anthropic API Client (OpenAI-Compatible)"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import httpx


API_VERSION = "2023-06-01"


def get_api_base_url() -> str:
    return os.environ.get("ANTHROPIC_API_BASE_URL", "https://api.anthropic.com/v1")


@dataclass
class Message:
    role: str
    content: str


@dataclass
class APIResponse:
    content: str
    model: str
    stop_reason: str
    usage: Dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0


class APIService:
    """Anthropic API 客户端，支持 OpenAI 兼容模式"""
    
    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._request_count = 0
        self._client = None

    def _get_client(self):
        """获取或创建 anthropic 客户端"""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
                base_url = get_api_base_url()
                self._client = AsyncAnthropic(api_key=self.api_key, base_url=base_url)
            except ImportError:
                raise RuntimeError("anthropic SDK not installed")
        return self._client

    async def send_message(
        self,
        messages: List[Message],
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        temperature: float = 1.0,
        system_prompt: Optional[str] = None,
    ) -> APIResponse:
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        
        import time
        start = time.time()
        self._request_count += 1
        
        client = self._get_client()
        
        # 构建消息
        chat_messages = []
        if system_prompt:
            chat_messages.append({"role": "user", "content": system_prompt})
        chat_messages.extend([{"role": m.role, "content": m.content} for m in messages])
        
        try:
            response = await client.messages.create(
                model=model,
                messages=chat_messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            
            # 提取内容
            content = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    content += block.text
            
            return APIResponse(
                content=content,
                model=response.model,
                stop_reason=response.stop_reason,
                usage={
                    "input_tokens": response.usage.input_tokens if hasattr(response, 'usage') else 0,
                    "output_tokens": response.usage.output_tokens if hasattr(response, 'usage') else 0,
                },
                latency_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            raise RuntimeError(f"API call failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        return {"request_count": self._request_count}


_api: Optional[APIService] = None


def get_api_service() -> APIService:
    global _api
    if _api is None:
        _api = APIService()
    return _api


__all__ = ["Message", "APIResponse", "APIService", "get_api_service"]
