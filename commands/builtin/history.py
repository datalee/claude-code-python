"""
HistoryCommand - 历史记录命令

对应 Claude Code 源码: src/commands/builtin/history.ts
"""

from __future__ import annotations

import os
from typing import List

from commands.base import Command, CommandContext, CommandResult


class HistoryCommand(Command):
    """显示命令历史"""

    name = "history"
    description = "Show command history"
    aliases = ["h"]
    usage = """/history [limit]
    Show recent command history.

Args:
  limit - Number of recent commands to show (default: 20, max: 100)"""

    async def execute(self, args: List[str], context: CommandContext) -> CommandResult:
        """执行历史查看命令"""
        import readline

        # 解析参数
        try:
            limit = int(args[0]) if args else 20
            limit = min(max(1, limit), 100)
        except ValueError:
            return CommandResult.err("Invalid limit. Use: /history [limit]")

        try:
            history_file = os.path.expanduser("~/.claude_code_history")
            
            lines_output = []
            
            # 尝试从文件读取
            if os.path.exists(history_file):
                with open(history_file, "r", encoding="utf-8") as f:
                    all_lines = f.readlines()
                
                # 显示最后 N 条
                start = max(0, len(all_lines) - limit)
                for i, line in enumerate(all_lines[start:], start=start + 1):
                    line = line.strip()
                    if line:
                        lines_output.append(f"  {i}: {line}")
            else:
                # 使用 readline
                total = readline.get_current_history_length()
                start = max(0, total - limit)
                
                for i in range(start + 1, total + 1):
                    item = readline.get_history_item(i)
                    if item:
                        lines_output.append(f"  {i}: {item}")
            
            if not lines_output:
                return CommandResult.ok("No history found.")
            
            output = f"\n=== Recent Commands ({len(lines_output)}) ===\n\n"
            output += "\n".join(lines_output)
            output += "\n"
            
            return CommandResult.ok(output)
        
        except Exception as e:
            return CommandResult.err(f"Error reading history: {e}")
