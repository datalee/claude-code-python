"""
SkillsCommand - Skill 管理命令

对应 Claude Code 源码: src/commands/skills/

功能：
- 列出可用 skills（从 ~/.claude/skills/ 加载）
- 显示 skill 详情
- /skill <name> 调用 skill
"""

from __future__ import annotations

from typing import List

from commands.base import Command, CommandContext, CommandResult
from agent.context import Message, MessageRole


class SkillsCommand(Command):
    """Skill 管理"""

    name = "skills"
    description = "Manage and invoke skills"
    aliases = ["skill"]
    usage = """/skills [list|show <name>]
    Manage skills loaded from ~/.claude/skills/

  /skills list        - List all available skills
  /skills show <name> - Show skill details
  /skill <name>       - Invoke a skill directly
  /skill <query>      - Auto-match and invoke best skill"""

    def __init__(self) -> None:
        self._skill_runner = None
    
    @property
    def runner(self):
        if self._skill_runner is None:
            from skill import get_skill_runner
            self._skill_runner = get_skill_runner()
        return self._skill_runner

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
                return self._show_skill(args[1])
            
            elif subcmd == "invoke":
                if len(args) < 2:
                    return CommandResult.err("Usage: /skills invoke <name>")
                return self._invoke_skill(args[1], context)
            
            else:
                # 可能是直接调用 skill
                return self._invoke_skill(subcmd, context)
        
        except Exception as e:
            return CommandResult.err(f"Skills error: {e}")

    def _list_skills(self) -> str:
        """列出所有 skills"""
        skills = self.runner.list_all()
        
        if not skills:
            lines = ["\n=== Available Skills ===\n"]
            lines.append("No skills loaded.")
            lines.append("")
            lines.append("Skills are loaded from ~/.claude/skills/")
            lines.append("Use /skills show <name> for details")
            lines.append("")
            return "\n".join(lines)
        
        lines = [f"\n=== Available Skills ({len(skills)}) ===\n"]
        
        for s in skills:
            triggers = s.get("triggers", "-")
            if triggers and triggers != "-":
                lines.append(f"  /{s['slug']}")
                lines.append(f"    {s['description']}")
                lines.append(f"    triggers: {triggers}")
                lines.append("")
            else:
                lines.append(f"  /{s['slug']} - {s['description']}")
        
        lines.append("")
        lines.append(f"Total: {len(skills)} skills")
        lines.append("Use /skills show <name> for details")
        lines.append("")
        return "\n".join(lines)

    def _show_skill(self, name: str) -> CommandResult:
        """显示 skill 详情"""
        from skill import get_skill_loader
        
        loader = get_skill_loader()
        skill = loader.get_skill(name)
        
        if not skill:
            return CommandResult.err(f"Skill not found: {name}")
        
        lines = [f"\n=== Skill: {skill.slug} ===\n"]
        lines.append(f"  Name: {skill.name}")
        lines.append(f"  Description: {skill.description}")
        lines.append(f"  Version: {skill.version}")
        if skill.triggers:
            lines.append(f"  Triggers: {', '.join(skill.triggers)}")
        lines.append("")
        lines.append("--- Content Preview ---")
        lines.append(skill.content[:500] + "..." if len(skill.content) > 500 else skill.content)
        lines.append("")
        
        return CommandResult.ok("\n".join(lines))

    def _invoke_skill(self, query: str, context: CommandContext) -> CommandResult:
        """调用 skill"""
        result = self.runner.invoke(query, {})
        
        if "error" in result:
            return CommandResult.err(result["error"])
        
        skill = result["skill"]
        prompt = result["prompt"]
        
        lines = [f"\n=== Invoking Skill: {skill.name} ===\n"]
        lines.append(f"  Description: {skill.description}")
        lines.append("")
        lines.append("Skill prompt loaded. It will be prepended to your next message.")
        lines.append("")
        
        # 将 skill prompt 存储到 context 以便下次使用
        context.engine.context.add_message(
            Message(role=MessageRole.SYSTEM, content=prompt)
        )
        
        return CommandResult.ok("\n".join(lines))


class SkillCommand(SkillsCommand):
    """Skill 命令的别名"""
    pass
