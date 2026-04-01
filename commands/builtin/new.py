"""
NewCommand - 开始新会话命令

对应 Claude Code 源码: src/commands/builtin/new.ts
"""

from __future__ import annotations

from typing import List

from commands.base import Command, CommandContext, CommandResult
from hook.events import EventType


class NewCommand(Command):
    """开始新会话"""

    name = "new"
    description = "Start a new session"
    aliases = ["n", "restart"]
    usage = """/new [name]
    Start a new session.
    Optionally provide a session name."""

    async def execute(self, args: List[str], context: CommandContext) -> CommandResult:
        """执行新会话命令"""
        # 提取会话名称
        session_name = args[0] if args else None
        
        # 发送命令事件
        if context.hook_registry:
            from hook.events import create_command_event
            event = create_command_event(
                command="new",
                args=args,
                session_id=context.session_id,
            )
            await context.hook_registry.emit(event)
        
        # 清除上下文
        if context.engine and context.engine.context:
            context.engine.context.clear()
        
        # 生成新会话 ID
        import uuid
        new_session_id = f"session_{uuid.uuid4().hex[:12]}"
        context.session_id = new_session_id
        
        # 更新 REPL 会话 ID
        if context.repl:
            context.repl.set_session_id(new_session_id)
        
        # 发送会话开始事件
        if context.hook_registry:
            from hook.events import create_session_event
            event = create_session_event(
                EventType.SESSION_START,
                session_id=new_session_id,
            )
            await context.hook_registry.emit(event)
        
        output = "New session started."
        if session_name:
            output += f" (session: {session_name})"
        
        return CommandResult.ok(output)
