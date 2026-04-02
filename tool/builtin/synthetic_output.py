"""
SyntheticOutputTool - Synthetic Output Tool

对应 Claude Code 源码: src/tools/SyntheticOutputTool/

功能：
- 生成合成输出
- 输出格式化内容
- 自定义输出样式
"""

from __future__ import annotations

from typing import Any, Dict

from tool.base import Tool, ToolResult, Permission, PermissionMode, PermissionScope


class SyntheticOutputTool(Tool):
    """
    Generate synthetic output content.
    
    对应 Claude Code 源码: src/tools/SyntheticOutputTool/
    """

    name = "synthetic_output"
    description = "Generate synthetic output content"
    permission = Permission(mode=PermissionMode.AUTOMATIC, scope=PermissionScope.READ)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["text", "code", "markdown", "json", "html"],
                    "description": "Output content type",
                },
                "content": {
                    "type": "string",
                    "description": "Content to output",
                },
                "language": {
                    "type": "string",
                    "description": "Language for code blocks (for code type)",
                },
            },
            "required": ["type", "content"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        output_type = input_data.get("type", "text")
        content = input_data.get("content", "")
        language = input_data.get("language", "")

        if not content:
            return ToolResult.error("content is required")

        try:
            if output_type == "text":
                return ToolResult.ok(content)

            elif output_type == "code":
                return ToolResult.ok(
                    f"```{language}\n{content}\n```"
                )

            elif output_type == "markdown":
                return ToolResult.ok(content)

            elif output_type == "json":
                import json
                # Validate JSON
                json.loads(content)
                return ToolResult.ok(content)

            elif output_type == "html":
                return ToolResult.ok(f"<div>{content}</div>")

            else:
                return ToolResult.error(f"Unknown type: {output_type}")

        except Exception as e:
            return ToolResult.error(f"Synthetic output error: {e}")
