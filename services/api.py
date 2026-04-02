"""API Service - Anthropic API Client"""
from __future__ import annotations
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
import httpx


API_BASE_URL = "https://api.anthropic.com/v1"
API_VERSION = "2023-06-01"


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
    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._request_count = 0
        self._base_url = API_BASE_URL

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
        
        start = time.time()
        self._request_count += 1
        
        # 构建请求头
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        }
        
        # 构建消息
        chat_messages = []
        if system_prompt:
            chat_messages.append({"role": "user", "content": system_prompt})
        chat_messages.extend([{"role": m.role, "content": m.content} for m in messages])
        
        # 构建请求体
        request_body = {
            "model": model,
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        # 发送请求
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._base_url}/messages",
                headers=headers,
                json=request_body,
            )
            
            if response.status_code != 200:
                raise RuntimeError(f"API error: {response.status_code} - {response.text}")
            
            data = response.json()
            
            # 解析响应
            content = ""
            if data.get("content"):
                for block in data["content"]:
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

    async def send_message_stream(
        self,
        messages: List[Message],
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        temperature: float = 1.0,
        system_prompt: Optional[str] = None,
    ):
        """流式发送消息（生成器）"""
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        
        headers = {
            "x-api-key": self.api_key,
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
            "stream": True,
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/messages",
                headers=headers,
                json=request_body,
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        import json as _json
                        try:
                            chunk = _json.loads(data)
                            if chunk.get("type") == "content_block_delta":
                                delta = chunk.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    yield delta.get("text", "")
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
