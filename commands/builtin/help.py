"""
HelpCommand - 帮助命令

对应 Claude Code 源码: src/commands/builtin/help.ts
"""

from __future__ import annotations

from typing import List

from commands.base import Command, CommandContext, CommandResult


class HelpCommand(Command):
    """显示帮助信息"""

    name = "help"
    description = "Show this help message"
    aliases = ["?"]
    usage = """/help [command]
    Show help for all commands or a specific command.

Examples:
  /help       - Show all commands
  /help new   - Show help for /new command"""

    async def execute(self, args: List[str], context: CommandContext) -> CommandResult:
        """执行帮助命令"""
        from commands.registry import get_command_registry
        
        registry = get_command_registry()
        
        # 显示特定命令帮助
        if args:
            cmd_name = args[0].lstrip("/").lower()
            cmd = registry.get(cmd_name)
            
            if cmd is None:
                return CommandResult.err(f"Unknown command: /{cmd_name}")
            
            output = self._format_command_help(cmd)
            return CommandResult.ok(output)
        
        # 显示所有命令
        output = self._format_all_help(registry)
        return CommandResult.ok(output)

    def _format_command_help(self, cmd) -> str:
        """格式化单个命令的帮助"""
        lines = [f"\n=== /{cmd.name} ===", ""]
        lines.append(cmd.description)
        
        if cmd.usage:
            lines.append("")
            for line in cmd.usage.split("\n"):
                lines.append(f"  {line}")
        
        if cmd.aliases:
            lines.append("")
            lines.append(f"Aliases: {', '.join('/' + a for a in cmd.aliases)}")
        
        lines.append("")
        return "\n".join(lines)

    def _format_all_help(self, registry) -> str:
        """格式化所有命令的帮助"""
        lines = [
            "\n=== Claude Code Commands ===",
            "",
            "Usage: /<command> [args]",
            "",
            "Commands:",
        ]
        
        # 按名称排序
        for name in sorted(registry.list_names()):
            cmd = registry.get_primary(name)
            if cmd:
                lines.append(f"  /{name:<12} {cmd.description}")
                for alias in cmd.aliases:
                    lines.append(f"  /{alias:<12} (alias)")
        
        lines.extend([
            "",
            "Type /help <command> for detailed help.",
            ""
        ])
        
        return "\n".join(lines)
