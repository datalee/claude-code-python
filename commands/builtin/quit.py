"""
QuitCommand - 退出命令

对应 Claude Code 源码: src/commands/builtin/quit.ts
"""

from __future__ import annotations

from typing import List

from commands.base import Command, CommandContext, CommandResult
from hook.events import EventType


class QuitCommand(Command):
    """退出 REPL"""

    name = "quit"
    description = "Exit the REPL"
    aliases = ["q", "exit"]
    usage = """/quit
    Exit the REPL.
Aliases: /q, /exit"""

    async def execute(self, args: List[str], context: CommandContext) -> CommandResult:
        """执行退出命令"""
        # 发送命令事件
        if context.hook_registry:
            from hook.events import create_command_event
            event = create_command_event(
                command="quit",
                args=args,
                session_id=context.session_id,
            )
            await context.hook_registry.emit(event)

        # 发送会话结束事件
        if context.hook_registry:
            from hook.events import create_session_event
            event = create_session_event(
                EventType.SESSION_END,
                session_id=context.session_id,
            )
            await context.hook_registry.emit(event)

        # 停止 REPL
        if context.repl:
            context.repl._running = False

        return CommandResult.ok("Goodbye!")
