"""API Service - Anthropic API Client (OpenAI-Compatible)"""
from __future__ import annotations
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
import httpx


API_VERSION = "2023-06-01"


def get_api_base_url() -> str:
    """获取 API Base URL"""
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


def _is_openai_compatible() -> bool:
    """检查是否使用 OpenAI 兼容模式（如 Volcengine）"""
    base_url = get_api_base_url()
    return "volces" in base_url or "openai" in base_url or "ark." in base_url


async def _call_openai_compatible(
    api_key: str,
    base_url: str,
    messages: List[Message],
    model: str,
    max_tokens: int,
    temperature: float,
    system_prompt: Optional[str] = None,
) -> APIResponse:
    """调用 OpenAI 兼容 API（如 Volcengine Ark）"""
    start = time.time()
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    # 构建消息
    chat_messages = []
    if system_prompt:
        chat_messages.append({"role": "system", "content": system_prompt})
    chat_messages.extend([{"role": m.role, "content": m.content} for m in messages])
    
    request_body = {
        "model": model,
        "messages": chat_messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    
    # OpenAI 兼容 URL (Volcengine 需要 /v1 前缀)
    if "/v1" not in base_url:
        url = f"{base_url}/v1/chat/completions"
    else:
        url = f"{base_url}/chat/completions"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, json=request_body)
        
        if response.status_code != 200:
            raise RuntimeError(f"API error: {response.status_code} - {response.text}")
        
        data = response.json()
        
        # 解析 OpenAI 格式响应
        content = ""
        if data.get("choices"):
            content = data["choices"][0].get("message", {}).get("content", "")
        
        return APIResponse(
            content=content,
            model=data.get("model", model),
            stop_reason=data.get("choices", [{}])[0].get("finish_reason", "stop"),
            usage={
                "input_tokens": data.get("usage", {}).get("prompt_tokens", 0),
                "output_tokens": data.get("usage", {}).get("completion_tokens", 0),
            },
            latency_ms=(time.time() - start) * 1000,
        )


async def _call_anthropic_api(
    api_key: str,
    base_url: str,
    messages: List[Message],
    model: str,
    max_tokens: int,
    temperature: float,
    system_prompt: Optional[str] = None,
) -> APIResponse:
    """调用原生 Anthropic API"""
    start = time.time()
    
    headers = {
        "x-api-key": api_key,
        "anthropic-version": API_VERSION,
        "content-type": "application/json",
    }
    
    chat_messages = []
    if system_prompt:
        chat_messages.append({"role": "user", "content": system_prompt})
    chat_messages.extend([{"role": m.role, "content": m.content} for m in messages])
    
    request_body = {
        "model": model,
        "messages": chat_messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    
    url = f"{base_url}/messages"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, json=request_body)
        
        if response.status_code != 200:
            raise RuntimeError(f"API error: {response.status_code} - {response.text}")
        
        data = response.json()
        
        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")
        
        return APIResponse(
            content=content,
            model=data.get("model", model),
            stop_reason=data.get("stop_reason", "complete"),
            usage={
                "input_tokens": data.get("usage", {}).get("input_tokens", 0),
                "output_tokens": data.get("usage", {}).get("output_tokens", 0),
            },
            latency_ms=(time.time() - start) * 1000,
        )


class APIService:
    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._request_count = 0
        self._base_url = get_api_base_url()

    def set_api_key(self, api_key: str) -> None:
        self.api_key = api_key

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
        
        self._request_count += 1
        
        if _is_openai_compatible():
            return await _call_openai_compatible(
                self.api_key, self._base_url, messages, model, max_tokens, temperature, system_prompt
            )
        else:
            return await _call_anthropic_api(
                self.api_key, self._base_url, messages, model, max_tokens, temperature, system_prompt
            )

    async def send_message_stream(
        self,
        messages: List[Message],
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        temperature: float = 1.0,
        system_prompt: Optional[str] = None,
    ):
        """流式发送消息（生成器）- OpenAI 兼容模式"""
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        chat_messages = []
        if system_prompt:
            chat_messages.append({"role": "system", "content": system_prompt})
        chat_messages.extend([{"role": m.role, "content": m.content} for m in messages])
        
        request_body = {
            "model": model,
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        
        # OpenAI 兼容 URL (Volcengine 需要 /v1 前缀)
        if "/v1" not in self._base_url:
            url = f"{self._base_url}/v1/chat/completions"
        else:
            url = f"{self._base_url}/chat/completions"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST", url, headers=headers, json=request_body
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        import json as _json
                        try:
                            chunk = _json.loads(data)
                            if chunk.get("choices"):
                                delta = chunk["choices"][0].get("delta", {})
                                if delta.get("content"):
                                    yield delta["content"]
                        except:
                            pass

    def get_stats(self) -> Dict[str, Any]:
        return {"request_count": self._request_count}


_api: Optional[APIService] = None


def get_api_service() -> APIService:
    global _api
    if _api is None:
        _api = APIService()
    return _api


__all__ = ["Message", "APIResponse", "APIService", "get_api_service"]
