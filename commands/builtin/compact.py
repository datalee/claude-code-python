"""
CompactCommand - 上下文压缩命令

对应 Claude Code 源码: src/commands/compact/

功能：
- 压缩对话上下文
- 减少 token 使用
- 保存压缩历史
"""

from __future__ import annotations

from typing import List

from commands.base import Command, CommandContext, CommandResult


class CompactCommand(Command):
    """上下文压缩"""

    name = "compact"
    description = "Compact conversation context to reduce tokens"
    aliases = []
    usage = """/compact
    Compact the current conversation context to reduce token usage.

This will:
  - Summarize older messages
  - Remove redundant context
  - Keep recent important messages
  - Reduce overall token count"""

    async def execute(self, args: List[str], context: CommandContext) -> CommandResult:
        """执行压缩命令"""
        try:
            lines = ["\n=== Context Compaction ===\n"]
            
            # 检查是否有上下文可压缩
            if not context.engine or not hasattr(context.engine, 'context'):
                return CommandResult.err("No context available to compact")
            
            # 获取当前 token 计数
            current_tokens = 0
            msg_count = 0
            
            if hasattr(context.engine.context, 'messages'):
                msg_count = len(context.engine.context.messages)
            
            if hasattr(context.engine.context, 'estimate_total_tokens'):
                current_tokens = context.engine.context.estimate_total_tokens()
            
            lines.append(f"Messages: {msg_count}")
            lines.append(f"Current tokens: ~{current_tokens}")
            lines.append("")
            
            # 执行压缩
            if hasattr(context.engine.context, 'compact'):
                result = context.engine.context.compact()
                if result:
                    new_tokens = context.engine.context.estimate_total_tokens()
                    saved = current_tokens - new_tokens
                    pct = (saved / current_tokens * 100) if current_tokens > 0 else 0
                    lines.append(f"Compact completed")
                    lines.append(f"Messages before: {msg_count}")
                    lines.append(f"Messages after: {len(context.engine.context.messages)}")
                    lines.append(f"Saved ~{saved} tokens ({pct:.1f}%)")
                else:
                    lines.append("No compaction needed")
                    lines.append("Context is already compact")
            else:
                lines.append("Context compaction not available")
                lines.append("The compact() method is not implemented in this context")
            
            lines.append("")
            return CommandResult.ok("\n".join(lines))
        
        except Exception as e:
            return CommandResult.err(f"Compact error: {e}")
