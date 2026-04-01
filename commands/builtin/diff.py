"""
DiffCommand - 显示变更命令

对应 Claude Code 源码: src/commands/diff/

功能：
- 显示 git diff
- 显示工作区变更
- 支持文件过滤
"""

from __future__ import annotations

import subprocess
from typing import List, Optional

from commands.base import Command, CommandContext, CommandResult


class DiffCommand(Command):
    """显示 git diff"""

    name = "diff"
    description = "Show git changes"
    aliases = ["d"]
    usage = """/diff [file]
    Show git changes.

Examples:
  /diff           - Show all changes
  /diff file.py    - Show changes for specific file"""

    def _run_git(self, args: List[str]) -> tuple[int, str, str]:
        """运行 git 命令"""
        try:
            result = subprocess.run(
                ["git", "diff"] + args,
                capture_output=True,
                text=True,
            )
            return result.returncode, result.stdout, result.stderr
        except FileNotFoundError:
            return 1, "", "git not found"
        except Exception as e:
            return 1, "", str(e)

    async def execute(self, args: List[str], context: CommandContext) -> CommandResult:
        """执行 diff 命令"""
        try:
            # 检查是否是 git 仓库
            code, _, stderr = self._run_git(["--no-ext-diff"])
            if code != 0 and "not a git repository" in stderr.lower():
                return CommandResult.err("Not a git repository")
            
            # 运行 diff
            returncode, stdout, stderr = self._run_git(args)
            
            if returncode != 0 and stderr:
                return CommandResult.err(f"git diff error: {stderr}")
            
            if not stdout:
                return CommandResult.ok("No changes detected.")
            
            return CommandResult.ok(stdout)
        
        except Exception as e:
            return CommandResult.err(f"Diff error: {e}")
