"""
SkillTool - Tool for invoking skills

对应 Claude Code 源码: src/tools/SkillTool/SkillTool.ts

SkillTool 是一个真正的 Tool，模型可以通过 function call 调用它。
当模型需要使用某个 skill 时，调用 Skill(skill="web-access", args="...")，
Tool 会加载 skill 的内容并返回给模型。

这是 skill 与 agent 循环配合的核心机制。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from agent.context import AgentContext
from tool.base import Tool, ToolResult


@dataclass
class SkillToolResult:
    """SkillTool 返回结果"""
    success: bool
    command_name: str
    allowed_tools: Optional[List[str]] = None
    model: Optional[str] = None
    new_messages: Optional[List[Dict[str, Any]]] = None


class SkillTool(Tool):
    """
    SkillTool - 允许模型通过 function call 调用 skills。
    
    当模型需要某个 skill 的能力时，调用这个 tool。
    Tool 会：
    1. 找到对应的 skill
    2. 加载 SKILL.md 内容
    3. 返回内容给模型，模型据此指导行动
    
    使用方式：
        Skill(skill="web-access", args="搜索 Python 教程")
    """
    
    name = "Skill"
    description = "Execute a skill by name. Skills provide specialized capabilities for specific tasks."
    
    def __init__(self):
        super().__init__()
        self._skill_loader = None
    
    @property
    def loader(self):
        """懒加载 skill loader"""
        if self._skill_loader is None:
            from skill import get_skill_loader
            self._skill_loader = get_skill_loader()
        return self._skill_loader
    
    def get_input_schema(self) -> Dict[str, Any]:
        """返回 tool 的输入 schema"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "skill": {
                        "type": "string",
                        "description": "The skill name (e.g., 'web-access', 'verify', 'commit')."
                    },
                    "args": {
                        "type": "string",
                        "description": "Optional arguments to pass to the skill."
                    }
                },
                "required": ["skill"]
            }
        }
    
    async def call(self, skill: str, args: Optional[str] = None, context: Optional["AgentContext"] = None) -> SkillToolResult:
        """
        调用 skill。
        
        Args:
            skill: skill 名称（不带前导斜杠）
            args: 可选的参数
            context: Agent 上下文
            
        Returns:
            SkillToolResult 包含 skill 内容和元数据
        """
        # 去掉前导斜杠
        skill_name = skill.lstrip("/")
        
        # 查找 skill
        loaded_skill = self.loader.get_skill(skill_name)
        
        if not loaded_skill:
            return SkillToolResult(
                success=False,
                command_name=skill_name,
                new_messages=[{
                    "role": "user",
                    "content": f"Skill not found: {skill_name}"
                }]
            )
        
        # 获取 skill 内容
        content = loaded_skill.content
        
        # 如果有 args，附加到内容
        if args:
            content = f"{content}\n\n## User Request\n\n{args}"
        
        # 构建返回消息
        new_messages = [{
            "role": "system" if loaded_skill.slug == "system" else "user",
            "content": f"[Skill: {loaded_skill.name}]\n\n{content}"
        }]
        
        return SkillToolResult(
            success=True,
            command_name=loaded_skill.name,
            new_messages=new_messages
        )
    
    def validate_skill(self, skill: str) -> tuple[bool, Optional[str]]:
        """
        验证 skill 是否存在。
        
        Returns:
            (is_valid, error_message)
        """
        skill_name = skill.lstrip("/")
        loaded_skill = self.loader.get_skill(skill_name)
        
        if not loaded_skill:
            return False, f"Unknown skill: {skill_name}"
        
        return True, None

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """
        执行 skill 调用。
        
        Args:
            input_data: 包含 skill 和可选 args 的字典
            
        Returns:
            ToolResult 包含 new_messages 在 metadata 中
        """
        skill = input_data.get("skill", "")
        args = input_data.get("args")
        
        # 去掉前导斜杠
        skill_name = skill.lstrip("/")
        
        # 查找 skill
        loaded_skill = self.loader.get_skill(skill_name)
        
        if not loaded_skill:
            return ToolResult.err(f"Skill not found: {skill_name}")
        
        # 获取 skill 内容
        content = loaded_skill.content
        
        # 如果有 args，附加到内容
        if args:
            content = f"{content}\n\n## User Request\n\n{args}"
        
        # 构建新消息
        new_messages = [{
            "role": "system" if loaded_skill.slug == "system" else "user",
            "content": f"[Skill: {loaded_skill.name}]\n\n{content}"
        }]
        
        # 返回 ToolResult，new_messages 放在 metadata 中
        return ToolResult(
            success=True,
            content=f"Skill loaded: {loaded_skill.name}",
            metadata={"new_messages": new_messages, "skill_name": loaded_skill.name}
        )


# 全局实例
_skill_tool: Optional[SkillTool] = None


def get_skill_tool() -> SkillTool:
    global _skill_tool
    if _skill_tool is None:
        _skill_tool = SkillTool()
    return _skill_tool


__all__ = ["SkillTool", "SkillToolResult", "get_skill_tool"]
