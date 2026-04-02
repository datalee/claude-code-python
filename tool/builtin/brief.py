"""
BriefTool - Summary Tool

对应 Claude Code 源码: src/tools/BriefTool/

功能：
- 生成简短摘要
- 压缩长文本
- 提取关键信息
"""

from __future__ import annotations

from typing import Any, Dict

from tool.base import Tool, ToolResult, Permission, PermissionMode, PermissionScope


class BriefTool(Tool):
    """
    Generate a brief summary of text.
    
    对应 Claude Code 源码: src/tools/BriefTool/
    """

    name = "brief"
    description = "Generate a brief summary of text"
    permission = Permission(mode=PermissionMode.AUTOMATIC, scope=PermissionScope.READ)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to summarize",
                },
                "max_length": {
                    "type": "integer",
                    "description": "Maximum length of summary (default: 100)",
                    "default": 100,
                },
            },
            "required": ["text"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        text = input_data.get("text", "")
        max_length = input_data.get("max_length", 100)

        if not text:
            return ToolResult.error("text is required")

        # 简单的摘要逻辑：
        # 1. 取前 max_length 个字符
        # 2. 在句子边界处截断
        if len(text) <= max_length:
            return ToolResult.ok(text)

        # 找最后一个句子边界
        truncated = text[:max_length]
        
        # 尝试在句号、问号、感叹号处截断
        for sep in ['。', '.', '!', '?', '\n']:
            last_sep = truncated.rfind(sep)
            if last_sep > max_length * 0.5:  # 至少要保留一半
                truncated = truncated[:last_sep + 1]
                break
        else:
            # 没找到句子边界，截断到最后一个完整单词
            last_space = truncated.rfind(' ')
            if last_space > max_length * 0.5:
                truncated = truncated[:last_space]

        return ToolResult.ok(truncated + "...")
