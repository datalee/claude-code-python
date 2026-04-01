"""
SkillsCommand - Skill 管理命令

对应 Claude Code 源码: src/commands/skills/

功能：
- 列出可用 skills
- 显示 skill 详情
- 启用/禁用 skill
- 加载/卸载 skill
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from commands.base import Command, CommandContext, CommandResult


# 内置 Skills 列表（基于我们的 skill 模块）
BUILTIN_SKILLS = {
    "hello_world": {
        "name": "Hello World",
        "description": "Example skill demonstrating basic functionality",
        "enabled": True,
    },
    "file_writer": {
        "name": "File Writer",
        "description": "Write content to files",
        "enabled": True,
    },
    "shell": {
        "name": "Shell Executor",
        "description": "Execute shell commands",
        "enabled": True,
    },
}


class SkillsCommand(Command):
    """Skill 管理"""

    name = "skills"
    description = "Manage available skills"
    aliases = []
    usage = """/skills
    Manage skills.

Commands:
  /skills list       - List all available skills
  /skills show <name> - Show skill details
  /skills enable <name> - Enable a skill
  /skills disable <name> - Disable a skill"""

    def __init__(self) -> None:
        self._skills: Dict[str, Dict[str, Any]] = BUILTIN_SKILLS.copy()

    async def execute(self, args: List[str], context: CommandContext) -> CommandResult:
        """执行 skills 命令"""
        try:
            if not args:
                return CommandResult.ok(self._list_skills())
            
            subcmd = args[0].lower()
            
            if subcmd == "list":
                return CommandResult.ok(self._list_skills())
            
            elif subcmd == "show":
                if len(args) < 2:
                    return CommandResult.err("Usage: /skills show <name>")
                return CommandResult.ok(self._show_skill(args[1]))
            
            elif subcmd == "enable":
                if len(args) < 2:
                    return CommandResult.err("Usage: /skills enable <name>")
                return CommandResult.ok(self._set_enabled(args[1], True))
            
            elif subcmd == "disable":
                if len(args) < 2:
                    return CommandResult.err("Usage: /skills disable <name>")
                return CommandResult.ok(self._set_enabled(args[1], False))
            
            else:
                return CommandResult.err(f"Unknown subcommand: {subcmd}")
        
        except Exception as e:
            return CommandResult.err(f"Skills error: {e}")

    def _list_skills(self) -> str:
        """列出所有 skills"""
        lines = ["\n=== Available Skills ===\n"]
        
        enabled = []
        disabled = []
        
        for name, skill in sorted(self._skills.items()):
            entry = f"  {name}: {skill['description']}"
            if skill.get("enabled", True):
                enabled.append(entry)
            else:
                disabled.append(entry)
        
        if enabled:
            lines.append("Enabled:")
            lines.extend(enabled)
            lines.append("")
        
        if disabled:
            lines.append("Disabled:")
            lines.extend(disabled)
            lines.append("")
        
        lines.append("Use /skills show <name> for details")
        lines.append("")
        return "\n".join(lines)

    def _show_skill(self, name: str) -> str:
        """显示 skill 详情"""
        if name not in self._skills:
            return f"\nSkill not found: {name}\n"
        
        skill = self._skills[name]
        lines = [f"\n=== Skill: {name} ===\n"]
        lines.append(f"  Name: {skill['name']}")
        lines.append(f"  Description: {skill['description']}")
        lines.append(f"  Enabled: {skill.get('enabled', True)}")
        lines.append("")
        return "\n".join(lines)

    def _set_enabled(self, name: str, enabled: bool) -> str:
        """启用/禁用 skill"""
        if name not in self._skills:
            return f"\nSkill not found: {name}\n"
        
        self._skills[name]["enabled"] = enabled
        status = "enabled" if enabled else "disabled"
        return f"\nSkill '{name}' {status}.\n"
