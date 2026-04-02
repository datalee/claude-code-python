"""
WebFetchTool - Fetch web pages and extract content

提供网页抓取能力，让模型可以获取网页内容。

对应 web-access skill 的核心需求。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from tool.base import Tool, ToolResult
import httpx


class WebFetchTool(Tool):
    """
    Fetch a web page and extract its content.
    
    模型可以用这个工具抓取网页、搜索结果等。
    """
    
    name = "web_fetch"
    description = "Fetch a web page and extract readable content. Use this for accessing web pages, reading articles, or getting information from URLs."
    
    def __init__(self):
        super().__init__()
        self.permission = self._create_permission()
    
    def _create_permission(self):
        from tool.base import Permission, PermissionMode, PermissionScope
        return Permission(mode=PermissionMode.AUTOMATIC, scope=PermissionScope.NETWORK)
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch"
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Maximum number of characters to return (default: 10000)",
                        "default": 10000
                    }
                },
                "required": ["url"]
            }
        }
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """
        执行网页抓取。
        """
        url = input_data.get("url", "")
        max_chars = input_data.get("max_chars", 10000)
        
        if not url:
            return ToolResult.err("URL is required")
        
        # 检查 URL 格式
        if not url.startswith(("http://", "https://")):
            return ToolResult.err(f"Invalid URL: {url}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, verify=False) as client:
                response = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                
                if response.status_code != 200:
                    return ToolResult.err(f"HTTP {response.status_code}")
                
                content_type = response.headers.get("content-type", "")
                
                # 只处理文本内容
                if "text/html" in content_type or "application/json" in content_type or "text/plain" in content_type:
                    text = response.text[:max_chars]
                    
                    # 简单的 HTML 清理
                    import re
                    # 移除 script 和 style 标签
                    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
                    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
                    # 移除 HTML 标签
                    text = re.sub(r'<[^>]+>', ' ', text)
                    # 清理空白
                    text = re.sub(r'\s+', ' ', text).strip()
                    
                    return ToolResult.ok(
                        f"Fetched: {url}\n\n{text[:max_chars]}",
                        url=url,
                        content_length=len(text)
                    )
                else:
                    return ToolResult.ok(
                        f"Fetched {url} ({content_type}, {len(response.content)} bytes)",
                        url=url,
                        content_type=content_type
                    )
        
        except httpx.TimeoutException:
            return ToolResult.err(f"Timeout fetching {url}")
        except Exception as e:
            return ToolResult.err(f"Error fetching {url}: {e}")


class WebSearchTool(Tool):
    """
    Search the web using a simple HTTP search API.
    
    如果没有专门的搜索 API，可以用 DuckDuckGo 或其他搜索。
    """
    
    name = "web_search"
    description = "Search the web and return results. Use this for finding information, looking up facts, or searching the internet."
    
    def __init__(self):
        super().__init__()
        self.permission = self._create_permission()
    
    def _create_permission(self):
        from tool.base import Permission, PermissionMode, PermissionScope
        return Permission(mode=PermissionMode.AUTOMATIC, scope=PermissionScope.NETWORK)
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """
        执行网页搜索。
        """
        query = input_data.get("query", "")
        max_results = input_data.get("max_results", 5)
        
        if not query:
            return ToolResult.err("Query is required")
        
        try:
            # 使用 DuckDuckGo HTML 搜索（不需要 API key）
            search_url = f"https://html.duckduckgo.com/html/?q={query}"
            
            async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                response = await client.get(search_url, headers={
                    "User-Agent": "Mozilla/5.0"
                })
                
                if response.status_code != 200:
                    return ToolResult.err(f"Search failed: HTTP {response.status_code}")
                
                # 解析 DuckDuckGo HTML 结果
                import re
                results = []
                
                # 找到搜索结果
                result_pattern = r'<a class="result__a" href="([^"]+)">([^<]+)</a>.*?<a class="result__snippet" href[^>]+>([^<]+)</a>'
                matches = re.findall(result_pattern, response.text, re.DOTALL)
                
                for url, title, snippet in matches[:max_results]:
                    results.append(f"**{title.strip()}**\n{snippet.strip()}\n{url}\n")
                
                if not results:
                    return ToolResult.ok(f"No results found for: {query}")
                
                return ToolResult.ok(
                    f"Search results for: {query}\n\n" + "\n---\n".join(results),
                    query=query,
                    result_count=len(results)
                )
        
        except Exception as e:
            return ToolResult.err(f"Search error: {e}")


class WeatherTool(Tool):
    """
    获取天气预报。使用 wttr.in 服务。
    """
    
    name = "weather"
    description = "Get weather forecast for a city. Use this to check current weather, forecasts, or weather conditions."
    
    def __init__(self):
        super().__init__()
        self.permission = self._create_permission()
    
    def _create_permission(self):
        from tool.base import Permission, PermissionMode, PermissionScope
        return Permission(mode=PermissionMode.AUTOMATIC, scope=PermissionScope.NETWORK)
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name (e.g., 'Shenzhen', 'Beijing', 'Shanghai')"
                    },
                    "format": {
                        "type": "string",
                        "description": "Format: '3' for one-line, '2' for two-line, '1' for verbose (default: '2')",
                        "default": "2"
                    }
                },
                "required": ["city"]
            }
        }
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """
        获取天气信息。
        """
        city = input_data.get("city", "")
        format_type = input_data.get("format", "2")
        
        if not city:
            return ToolResult.err("City is required")
        
        try:
            url = f"https://wttr.in/{city}?format={format_type}"
            
            async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                response = await client.get(url)
                
                if response.status_code != 200:
                    return ToolResult.err(f"Weather service error: HTTP {response.status_code}")
                
                # wttr.in 返回纯文本天气信息
                weather_text = response.text.strip()
                
                return ToolResult.ok(
                    f"Weather for {city}:\n{weather_text}",
                    city=city,
                    source="wttr.in"
                )
        
        except Exception as e:
            return ToolResult.err(f"Weather error: {e}")
