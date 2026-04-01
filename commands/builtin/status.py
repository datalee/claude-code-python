"""
StatusCommand - 状态查看命令

对应 Claude Code 源码: src/commands/builtin/status.ts
"""

from __future__ import annotations

from typing import List

from commands.base import Command, CommandContext, CommandResult


class StatusCommand(Command):
    """显示当前状态"""

    name = "status"
    description = "Show current session status"
    aliases = ["s"]
    usage = """/status
    Show current session status including:
  - Session ID
  - Current state (idle/running/error)
  - Iteration count
  - Message count
  - Current model"""

    async def execute(self, args: List[str], context: CommandContext) -> CommandResult:
        """执行状态查看命令"""
        lines = ["\n=== Session Status ===", ""]
        
        # 会话 ID
        lines.append(f"Session ID:   {context.session_id or 'N/A'}")
        
        # 引擎状态
        if context.engine:
            state = getattr(context.engine, 'state', None)
            if state:
                state_value = state.value if hasattr(state, 'value') else str(state)
                lines.append(f"State:        {state_value}")
            
            # 迭代次数
            iteration = getattr(context.engine, 'iteration', 0)
            lines.append(f"Iterations:  {iteration}")
            
            # 消息数
            if hasattr(context.engine, 'context') and context.engine.context:
                msg_count = len(context.engine.context.messages) if hasattr(context.engine.context, 'messages') else 0
                lines.append(f"Messages:     {msg_count}")
            
            # 当前模型
            if hasattr(context.engine, 'config') and context.engine.config:
                model = context.engine.config.model
                lines.append(f"Model:        {model}")
        else:
            lines.append("Engine:       N/A")
        
        # Token 统计
        if context.cost_tracker:
            total_cost = getattr(context.cost_tracker, 'total_cost', 0)
            lines.append(f"Total cost:   ${total_cost:.4f}")
        
        lines.append("")
        return CommandResult.ok("\n".join(lines))
