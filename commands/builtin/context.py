"""
ContextCommand - 上下文查看命令

对应 Claude Code 源码: src/commands/context/

功能：
- 显示当前上下文状态
- 显示消息列表
- 显示 token 使用量
- 显示上下文窗口使用率
"""

from __future__ import annotations

from typing import List

from commands.base import Command, CommandContext, CommandResult


class ContextCommand(Command):
    """查看上下文状态"""

    name = "context"
    description = "Show conversation context status"
    aliases = ["ctx"]
    usage = """/context
    Show current conversation context status.

Displays:
  - Message count
  - Token usage
  - Context window utilization
  - Recent messages"""

    async def execute(self, args: List[str], context: CommandContext) -> CommandResult:
        """执行上下文查看命令"""
        try:
            lines = ["\n=== Context Status ===\n"]
            
            # 会话信息
            lines.append(f"Session ID: {context.session_id}")
            lines.append("")
            
            # 引擎信息
            if context.engine:
                # 消息数量
                msg_count = 0
                token_count = 0
                
                if hasattr(context.engine, 'context') and context.engine.context:
                    if hasattr(context.engine.context, 'messages'):
                        msg_count = len(context.engine.context.messages)
                    if hasattr(context.engine.context, 'estimate_total_tokens'):
                        token_count = context.engine.context.estimate_total_tokens()
                
                lines.append(f"Messages: {msg_count}")
                lines.append(f"Estimated Tokens: {token_count}")
                
                # 迭代次数
                iteration = getattr(context.engine, 'iteration', 0)
                lines.append(f"Iterations: {iteration}")
                
                # 当前模型
                if hasattr(context.engine, 'config') and context.engine.config:
                    model = context.engine.config.model
                    lines.append(f"Model: {model}")
            else:
                lines.append("Engine: N/A")
            
            # Token 统计
            if context.cost_tracker:
                lines.append("")
                lines.append("Token Usage:")
                
                # 从 cost_tracker 获取统计
                if hasattr(context.cost_tracker, 'usage_by_model') and context.cost_tracker.usage_by_model:
                    for model, usage in context.cost_tracker.usage_by_model.items():
                        input_tokens = getattr(usage, 'input_tokens', 0)
                        output_tokens = getattr(usage, 'output_tokens', 0)
                        lines.append(f"  {model}:")
                        lines.append(f"    Input:  {input_tokens} tokens")
                        lines.append(f"    Output: {output_tokens} tokens")
                else:
                    lines.append("  No usage data")
            
            lines.append("")
            return CommandResult.ok("\n".join(lines))
        
        except Exception as e:
            return CommandResult.err(f"Context error: {e}")
