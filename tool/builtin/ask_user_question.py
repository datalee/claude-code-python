"""
AskUserQuestionTool - User Question Tool

对应 Claude Code 源码: src/tools/AskUserQuestionTool/

功能：
- 向用户提问
- 获取用户输入
- 支持多种问题类型
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from tool.base import Tool, ToolResult, Permission, PermissionMode, PermissionScope


class AskUserQuestionTool(Tool):
    """
    Ask the user a question and return their response.
    
    对应 Claude Code 源码: src/tools/AskUserQuestionTool/
    
    注意：这个工具在纯异步环境中无法直接获取用户输入，
    通常需要通过 REPL 或其他交互式界面来实现。
    """

    name = "ask_user_question"
    description = "Ask the user a question and get their response"
    permission = Permission(mode=PermissionMode.ASK, scope=PermissionScope.ALL)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to ask the user",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of choices for the user to pick from",
                },
                "default": {
                    "type": "string",
                    "description": "Default answer if user just presses enter",
                },
            },
            "required": ["question"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        question = input_data.get("question", "")
        options = input_data.get("options", [])
        default = input_data.get("default", "")

        if not question:
            return ToolResult.error("question is required")

        # 构建问题文本
        prompt = f"\n{question}"
        
        if options:
            prompt += "\nOptions:"
            for i, opt in enumerate(options, 1):
                prompt += f"\n  [{i}] {opt}"
            if default:
                prompt += f"\n(Default: {default})"
        elif default:
            prompt += f"\n(Default: {default})"
        
        prompt += "\n> "

        # 返回问题，让调用者决定如何获取用户输入
        # 在实际的 REPL 环境中，这会被重定向到用户输入
        return ToolResult.ok(
            content=f"[QUESTION] {question}",
            metadata={
                "question": question,
                "options": options,
                "default": default,
                "prompt": prompt,
                "requires_input": True,
            }
        )

    def format_question(self, question: str, options: List[str], default: str) -> str:
        """格式化问题文本"""
        lines = [f"\n{question}"]
        
        if options:
            lines.append("\nOptions:")
            for i, opt in enumerate(options, 1):
                lines.append(f"  [{i}] {opt}")
        
        if default:
            lines.append(f"\n(Default: {default})")
        
        lines.append("\n> ")
        return "\n".join(lines)
