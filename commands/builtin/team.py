"""
TeamCommand - Team 管理命令

对应 Claude Code 源码: src/commands/team/

功能：
- 创建 Team
- 列出 Team 成员
- Team 协作状态
- 添加/移除成员
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from commands.base import Command, CommandContext, CommandResult


@dataclass
class TeamMember:
    """团队成员"""
    id: str
    name: str
    role: str = "member"  # owner, admin, member
    status: str = "offline"  # online, offline, busy
    joined_at: float = field(default_factory=time.time)


class Team:
    """团队"""
    def __init__(self, name: str) -> None:
        self.name = name
        self.members: Dict[str, TeamMember] = {}
        self.created_at = time.time()


class TeamCommand(Command):
    """Team 管理"""

    name = "team"
    description = "Manage team collaboration"
    aliases = []
    usage = """/team
    Manage team collaboration.

Commands:
  /team list      - List team members
  /team create <name> - Create a team
  /team add <name> <role> - Add member
  /team remove <name> - Remove member
  /team status   - Show team status"""

    def __init__(self) -> None:
        self._teams: Dict[str, Team] = {}
        self._current_team: Optional[Team] = None

    async def execute(self, args: List[str], context: CommandContext) -> CommandResult:
        """执行 team 命令"""
        try:
            if not args:
                return CommandResult.ok(self._show_status())
            
            subcmd = args[0].lower()
            
            if subcmd == "list":
                return CommandResult.ok(self._list_members())
            
            elif subcmd == "create":
                if len(args) < 2:
                    return CommandResult.err("Usage: /team create <name>")
                return CommandResult.ok(self._create_team(args[1]))
            
            elif subcmd == "add":
                if len(args) < 2:
                    return CommandResult.err("Usage: /team add <name> [role]")
                role = args[2] if len(args) > 2 else "member"
                return CommandResult.ok(self._add_member(args[1], role))
            
            elif subcmd == "remove":
                if len(args) < 2:
                    return CommandResult.err("Usage: /team remove <name>")
                return CommandResult.ok(self._remove_member(args[1]))
            
            elif subcmd == "status":
                return CommandResult.ok(self._show_status())
            
            else:
                return CommandResult.err(f"Unknown subcommand: {subcmd}")
        
        except Exception as e:
            return CommandResult.err(f"Team error: {e}")

    def _list_members(self) -> str:
        """列出成员"""
        if not self._current_team:
            return "\nNo team selected. Create one with /team create <name>\n"
        
        team = self._current_team
        lines = [f"\n=== Team: {team.name} ===\n"]
        
        if not team.members:
            lines.append("  No members")
        else:
            for member in team.members.values():
                status_icon = "🟢" if member.status == "online" else "⚪"
                lines.append(f"  {status_icon} {member.name} ({member.role})")
        
        lines.append("")
        return "\n".join(lines)

    def _create_team(self, name: str) -> str:
        """创建团队"""
        if name in self._teams:
            return f"\nTeam '{name}' already exists. Use /team select {name}\n"
        
        team = Team(name)
        self._teams[name] = team
        self._current_team = team
        
        return f"\nTeam '{name}' created and selected.\n"

    def _add_member(self, name: str, role: str = "member") -> str:
        """添加成员"""
        if not self._current_team:
            return "\nNo team selected. Create one with /team create <name>\n"
        
        member_id = f"member_{len(self._current_team.members) + 1}"
        member = TeamMember(id=member_id, name=name, role=role)
        self._current_team.members[member_id] = member
        
        return f"\nMember '{name}' added as {role}.\n"

    def _remove_member(self, name: str) -> str:
        """移除成员"""
        if not self._current_team:
            return "\nNo team selected.\n"
        
        # Find by name
        to_remove = None
        for mid, member in self._current_team.members.items():
            if member.name == name:
                to_remove = mid
                break
        
        if to_remove:
            del self._current_team.members[to_remove]
            return f"\nMember '{name}' removed.\n"
        
        return f"\nMember '{name}' not found.\n"

    def _show_status(self) -> str:
        """显示状态"""
        lines = ["\n=== Team Status ===\n"]
        
        if not self._teams:
            lines.append("  No teams. Create one with /team create <name>")
        else:
            lines.append(f"  Teams: {len(self._teams)}")
            for name, team in self._teams.items():
                current = " (selected)" if team is self._current_team else ""
                lines.append(f"    - {name}{current} ({len(team.members)} members)")
        
        if self._current_team:
            lines.append("")
            lines.append(f"  Current team: {self._current_team.name}")
            lines.append(f"  Members: {len(self._current_team.members)}")
        
        lines.append("")
        return "\n".join(lines)
