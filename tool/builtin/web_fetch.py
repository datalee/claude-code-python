"""
WebFetchTool - 网页内容抓取

获取网页内容并提取可读文本。
对应 Claude Code 内置工具: WebFetchTool
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from tool.base import Tool, ToolResult, Permission, PermissionScope, PermissionMode


class WebFetchTool(Tool):
    """
    Fetch a web page and extract its content.

    Features:
    - Extract readable text content (removes ads, navigation, etc.)
    - Supports HTML parsing
    - Returns title and content
    - Max content length to avoid huge responses

    示例：
        web_fetch(url="https://example.com/article")
        web_fetch(url="https://news.site.com", max_chars=5000)
    """

    name = "web_fetch"
    description = "Fetch a web page and extract its readable content."
    permission = Permission(mode=PermissionMode.ASK, scope=PermissionScope.NETWORK)

    def __init__(self):
        super().__init__()
        self._html_parser = None

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch",
                    "format": "uri",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum number of characters to return",
                    "default": 10000,
                    "minimum": 100,
                    "maximum": 50000,
                },
                "extract_links": {
                    "type": "boolean",
                    "description": "Extract links from the page",
                    "default": False,
                },
            },
            "required": ["url"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        url = input_data["url"]
        max_chars = input_data.get("max_chars", 10000)
        extract_links = input_data.get("extract_links", False)

        # 验证 URL
        if not self._is_valid_url(url):
            return ToolResult.err(f"Invalid URL: {url}")

        try:
            result = await self._fetch(url, max_chars, extract_links)
            return ToolResult.ok(result)

        except Exception as e:
            return ToolResult.err(f"Web fetch error: {e}")

    def _is_valid_url(self, url: str) -> bool:
        """验证 URL 格式"""
        try:
            result = urlparse(url)
            return all([result.scheme in ("http", "https"), result.netloc])
        except Exception:
            return False

    async def _fetch(self, url: str, max_chars: int, extract_links: bool) -> str:
        """抓取网页并提取内容"""
        import aiohttp

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; Claude/1.0; +https://anthropic.com)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return f"HTTP {resp.status}: {resp.reason}"

                content_type = resp.headers.get("Content-Type", "")
                if "text/html" not in content_type:
                    # 非 HTML 内容，直接返回
                    text = await resp.text()
                    return text[:max_chars]

                html = await resp.text()

        # 解析 HTML
        title, text = self._extract_content(html, max_chars)

        result_parts = []

        if title:
            result_parts.append(f"# {title}\n")

        result_parts.append(text)

        if extract_links:
            links = self._extract_links(html, url)
            if links:
                result_parts.append("\n## Links\n")
                for link in links[:20]:  # 最多 20 个链接
                    result_parts.append(f"- {link['text']}: {link['href']}")

        return "".join(result_parts)

    def _extract_content(self, html: str, max_chars: int) -> tuple[Optional[str], str]:
        """从 HTML 中提取内容和标题"""
        # 提取标题
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else None

        # 移除脚本和样式
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

        # 移除 HTML 标签
        text = re.sub(r"<[^>]+>", " ", html)

        # 解码 HTML 实体
        text = self._decode_html_entities(text)

        # 规范化空白
        text = re.sub(r"\s+", " ", text)

        # 去除多余空白
        text = text.strip()

        # 截断
        if len(text) > max_chars:
            text = text[:max_chars] + "..."

        return title, text

    def _decode_html_entities(self, text: str) -> str:
        """解码 HTML 实体"""
        entities = {
            "&nbsp;": " ",
            "&amp;": "&",
            "&lt;": "<",
            "&gt;": ">",
            "&quot;": '"',
            "&#39;": "'",
            "&apos;": "'",
            "&mdash;": "—",
            "&ndash;": "–",
            "&hellip;": "...",
            "&copy;": "©",
            "&reg;": "®",
            "&trade;": "™",
        }

        for entity, char in entities.items():
            text = text.replace(entity, char)

        # 通用数字实体
        text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
        text = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), text)

        return text

    def _extract_links(self, html: str, base_url: str) -> list:
        """从 HTML 中提取链接"""
        from urllib.parse import urljoin

        links = []

        # 提取所有 href
        href_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
        text_pattern = re.compile(r'>([^<]+)<')

        # 简单实现：找到所有 <a> 标签
        a_pattern = re.compile(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>([^<]*)</a>", re.IGNORECASE)

        for match in a_pattern.finditer(html):
            href = match.group(1)
            link_text = match.group(2).strip()

            # 跳过空链接和锚点
            if not href or href.startswith("#"):
                continue

            # 跳过 javascript 和 mailto
            if href.startswith(("javascript:", "mailto:", "tel:")):
                continue

            # 转为绝对 URL
            abs_url = urljoin(base_url, href)

            links.append({
                "href": abs_url,
                "text": link_text or abs_url,
            })

        return links
