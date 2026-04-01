"""
ClearCommand - 清屏命令

对应 Claude Code 源码: src/commands/clear/clear.ts
"""

from __future__ import annotations

import os
import sys
from typing import List

from commands.base import Command, CommandContext, CommandResult


class ClearCommand(Command):
    """清屏 + 清空对话上下文"""

    name = "clear"
    description = "Clear the conversation context and terminal"
    aliases = ["cl"]
    usage = """/clear
    Clear the conversation context and terminal screen.
    This clears all messages and resets the session state.
Aliases: /cl"""

    async def execute(self, args: List[str], context: CommandContext) -> CommandResult:
        """执行清屏 + 清空上下文命令"""
        try:
            # 1. 清空 AgentContext 中的消息
            if context.engine and hasattr(context.engine, 'context'):
                context.engine.context.clear()
            
            # 2. 清空会话中的消息列表
            if context.engine and hasattr(context.engine, 'context'):
                if hasattr(context.engine.context, 'messages'):
                    context.engine.context.messages = []
            
            # 3. 重置迭代计数
            if context.engine:
                context.engine.iteration = 0
            
            # 4. 跨平台清屏
            if sys.platform == "win32":
                os.system("cls")
            else:
                os.system("clear")
            
            return CommandResult.ok("Conversation cleared.")
        
        except Exception as e:
            return CommandResult.err(f"Failed to clear: {e}")
