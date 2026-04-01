"""
ResetCommand - 重置会话命令

对应 Claude Code 源码: src/commands/builtin/reset.ts
"""

from __future__ import annotations

from typing import List

from commands.base import Command, CommandContext, CommandResult
from hook.events import EventType


class ResetCommand(Command):
    """重置当前会话"""

    name = "reset"
    description = "Reset the current session"
    aliases = ["r"]
    usage = """/reset
    Reset the current session, clearing all context."""

    async def execute(self, args: List[str], context: CommandContext) -> CommandResult:
        """执行重置命令"""
        # 发送命令事件
        if context.hook_registry:
            from hook.events import create_command_event
            event = create_command_event(
                command="reset",
                args=args,
                session_id=context.session_id,
            )
            await context.hook_registry.emit(event)
        
        # 清除上下文
        if context.engine and context.engine.context:
            context.engine.context.clear()
        
        # 重置迭代计数
        if context.engine:
            context.engine.iteration = 0
        
        # 发送会话开始事件（新会话）
        if context.hook_registry:
            from hook.events import create_session_event
            event = create_session_event(
                EventType.SESSION_START,
                session_id=context.session_id,
            )
            await context.hook_registry.emit(event)
        
        return CommandResult.ok("Session reset.")
