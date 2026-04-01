"""
WebSearchTool - 网络搜索

使用搜索引擎搜索查询。
对应 Claude Code 内置工具: WebSearchTool
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from tool.base import Tool, ToolResult, Permission, PermissionScope, PermissionMode


class WebSearchTool(Tool):
    """
    Search the web for information.

    Supports multiple search backends:
    - Brave Search (via BRAVE_API_KEY)
    - DuckDuckGo (fallback, no API key needed)
    - Google Custom Search (via GOOGLE_API_KEY)

    示例：
        web_search(query="Python async tutorial")
        web_search(query="latest AI news", count=5)
    """

    name = "web_search"
    description = "Search the web for information. Returns titles, URLs, and snippets."
    permission = Permission(mode=PermissionMode.ASK, scope=PermissionScope.NETWORK)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
                "count": {
                    "type": "integer",
                    "description": "Number of results to return",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 20,
                },
                "source": {
                    "type": "string",
                    "description": "Search source: 'brave', 'duckduckgo', or 'google'",
                    "default": "auto",
                },
            },
            "required": ["query"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        query = input_data["query"]
        count = input_data.get("count", 5)
        source = input_data.get("source", "auto")

        try:
            # 选择搜索后端
            if source == "auto":
                source = self._detect_source()

            if source == "brave":
                return await self._brave_search(query, count)
            elif source == "duckduckgo":
                return await self._duckduckgo_search(query, count)
            elif source == "google":
                return await self._google_search(query, count)
            else:
                return ToolResult.err(f"Unknown search source: {source}")

        except Exception as e:
            return ToolResult.err(f"Web search error: {e}")

    def _detect_source(self) -> str:
        """检测可用的搜索后端"""
        # 优先使用 Brave
        if os.environ.get("BRAVE_API_KEY"):
            return "brave"
        # 其次 Google
        if os.environ.get("GOOGLE_API_KEY"):
            return "google"
        # 最后 DuckDuckGo
        return "duckduckgo"

    async def _brave_search(self, query: str, count: int) -> ToolResult:
        """使用 Brave Search API"""
        import aiohttp

        api_key = os.environ.get("BRAVE_API_KEY")
        url = "https://api.search.brave.com/res/v1/web/search"

        headers = {
            "X-Subscription-Token": api_key,
            "Accept": "application/json",
        }

        params = {
            "q": query,
            "count": count,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        return ToolResult.err(f"Brave API error {resp.status}: {text}")

                    data = await resp.json()

            results = data.get("web", {}).get("results", [])
            output = self._format_results(results)
            return ToolResult.ok(output)

        except ImportError:
            return ToolResult.err("aiohttp not installed. Run: pip install aiohttp")
        except Exception as e:
            return ToolResult.err(f"Brave search failed: {e}")

    async def _duckduckgo_search(self, query: str, count: int) -> ToolResult:
        """使用 DuckDuckGo（无需 API key）"""
        try:
            # 使用 duckduckgo-search 包
            from duckduckgo_search import AsyncDDGS

            async with AsyncDDGS() as ddgs:
                results = []
                async for r in ddgs.text(query, max_results=count):
                    results.append(r)

            output = self._format_results(results)
            return ToolResult.ok(output)

        except ImportError:
            return ToolResult.err("duckduckgo-search not installed. Run: pip install duckduckgo-search")
        except Exception as e:
            return ToolResult.err(f"DuckDuckGo search failed: {e}")

    async def _google_search(self, query: str, count: int) -> ToolResult:
        """使用 Google Custom Search API"""
        import aiohttp

        api_key = os.environ.get("GOOGLE_API_KEY")
        cx = os.environ.get("GOOGLE_CSE_ID")  # Search Engine ID

        if not api_key or not cx:
            return ToolResult.err("GOOGLE_API_KEY and GOOGLE_CSE_ID required for Google search")

        url = "https://www.googleapis.com/customsearch/v1"

        params = {
            "key": api_key,
            "cx": cx,
            "q": query,
            "num": min(count, 10),
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        return ToolResult.err(f"Google API error {resp.status}: {text}")

                    data = await resp.json()

            items = data.get("items", [])
            output = self._format_results(items)
            return ToolResult.ok(output)

        except ImportError:
            return ToolResult.err("aiohttp not installed. Run: pip install aiohttp")
        except Exception as e:
            return ToolResult.err(f"Google search failed: {e}")

    def _format_results(self, results: List[Dict[str, Any]]) -> str:
        """格式化搜索结果"""
        if not results:
            return "No results found."

        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            url = r.get("url", r.get("link", ""))
            snippet = r.get("snippet", r.get("description", ""))

            lines.append(f"{i}. {title}")
            lines.append(f"   {url}")
            if snippet:
                lines.append(f"   {snippet[:200]}{'...' if len(snippet) > 200 else ''}")
            lines.append("")

        return "\n".join(lines[:-1]) if lines else "No results found."
