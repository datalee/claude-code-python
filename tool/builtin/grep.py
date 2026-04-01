"""
GrepTool - 代码内容搜索

在文件中搜索匹配的文本行。
对应 Claude Code 内置工具: GrepTool
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from tool.base import Tool, ToolResult, Permission, PermissionScope, PermissionMode


class GrepTool(Tool):
    """
    在代码文件中搜索匹配的文本。

    支持：
    - 简单字符串搜索
    - 正则表达式搜索
    - 上下文行（显示匹配行前后的内容）
    - 文件类型过滤
    - 递归搜索目录

    示例：
        # 搜索 "function hello"
        grep(query="function hello", path="./src")

        # 正则表达式搜索
        grep(query=r"\\d{4}-\\d{2}-\\d{2}", path=".", regex=true)

        # 带上下文
        grep(query="TODO", path=".", context=3)
    """

    name = "grep"
    description = "Search for matching patterns in files. Returns file paths and line numbers with context."
    permission = Permission(mode=PermissionMode.AUTOMATIC, scope=PermissionScope.READ)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The text or regex pattern to search for",
                },
                "path": {
                    "type": "string",
                    "description": "Directory or file path to search in (default: current directory)",
                    "default": ".",
                },
                "regex": {
                    "type": "boolean",
                    "description": "Whether query is a regular expression",
                    "default": False,
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Case sensitive matching",
                    "default": True,
                },
                "context": {
                    "type": "integer",
                    "description": "Number of context lines before/after match",
                    "default": 0,
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Only search in files matching this glob pattern (e.g., '*.py')",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 100,
                },
            },
            "required": ["query"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        query = input_data["query"]
        path = input_data.get("path", ".")
        regex = input_data.get("regex", False)
        case_sensitive = input_data.get("case_sensitive", True)
        context = input_data.get("context", 0)
        file_pattern = input_data.get("file_pattern")
        max_results = input_data.get("max_results", 100)

        try:
            # 解析路径
            search_path = Path(path)
            if not search_path.exists():
                return ToolResult.err(f"Path does not exist: {path}")

            # 编译正则
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                if regex:
                    pattern = re.compile(query, flags)
                else:
                    # 转义特殊字符，按字面量搜索
                    pattern = re.compile(re.escape(query), flags)
            except re.error as e:
                return ToolResult.err(f"Invalid regex: {e}")

            # 收集匹配结果
            matches: List[Dict[str, Any]] = []
            total_matches = 0

            # 如果是文件，直接搜索
            if search_path.is_file():
                files_to_search = [search_path]
            else:
                # 递归搜索目录
                files_to_search = []
                for f in search_path.rglob("*"):
                    if f.is_file():
                        if file_pattern:
                            if not f.match(file_pattern):
                                continue
                        # 跳过二进制文件
                        if self._is_binary(f):
                            continue
                        files_to_search.append(f)

            for file_path in files_to_search:
                if total_matches >= max_results:
                    break

                try:
                    file_matches = await self._search_file(
                        file_path, pattern, context, max_results - total_matches
                    )
                    matches.extend(file_matches)
                    total_matches += len(file_matches)
                except Exception as e:
                    # 跳过无法读取的文件
                    continue

            # 格式化输出
            if not matches:
                return ToolResult.ok("No matches found.")

            output = self._format_matches(matches, query)
            return ToolResult.ok(output, file_count=len(set(m["file"] for m in matches)))

        except Exception as e:
            return ToolResult.err(f"Grep error: {e}")

    async def _search_file(
        self,
        file_path: Path,
        pattern: re.Pattern,
        context: int,
        max_matches: int,
    ) -> List[Dict[str, Any]]:
        """在单个文件中搜索"""
        matches = []

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return matches

        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            if pattern.search(line):
                matches.append({
                    "file": str(file_path),
                    "line": i,
                    "content": line.rstrip(),
                })

                if len(matches) >= max_matches:
                    break

        return matches

    def _format_matches(self, matches: List[Dict[str, Any]], query: str) -> str:
        """格式化匹配结果"""
        if not matches:
            return "No matches found."

        # 按文件分组
        by_file: Dict[str, List[Dict[str, Any]]] = {}
        for m in matches:
            f = m["file"]
            if f not in by_file:
                by_file[f] = []
            by_file[f].append(m)

        lines = []
        for file_path, file_matches in by_file.items():
            lines.append(f"{file_path}:")
            for m in file_matches:
                lines.append(f"  {m['line']}: {m['content']}")
            lines.append("")

        return "\n".join(lines[:-1]) if lines else "No matches found."

    @staticmethod
    def _is_binary(file_path: Path) -> bool:
        """检查是否为二进制文件"""
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(1024)
                # 检查是否有空字节（文本文件中很少出现）
                return b"\0" in chunk
        except Exception:
            return True
