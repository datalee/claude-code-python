"""
ClearCommand - 清屏命令

对应 Claude Code 源码: src/commands/builtin/clear.ts
"""

from __future__ import annotations

import os
import sys
from typing import List

from commands.base import Command, CommandContext, CommandResult


class ClearCommand(Command):
    """清屏"""

    name = "clear"
    description = "Clear the screen"
    aliases = ["cl"]
    usage = """/clear
    Clear the terminal screen.
Aliases: /cl"""

    async def execute(self, args: List[str], context: CommandContext) -> CommandResult:
        """执行清屏命令"""
        try:
            # 跨平台清屏
            if sys.platform == "win32":
                os.system("cls")
            else:
                os.system("clear")
            
            return CommandResult.ok("")
        
        except Exception as e:
            return CommandResult.err(f"Failed to clear screen: {e}")
