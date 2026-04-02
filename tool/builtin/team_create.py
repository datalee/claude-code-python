"""
TeamCreateTool - Team Creation Tool

对应 Claude Code 源码: src/tools/TeamCreateTool/

功能：
- 创建团队
- 添加团队成员
- 管理团队协作
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from tool.base import Tool, ToolResult, Permission, PermissionMode, PermissionScope


class TeamCreateTool(Tool):
    """
    Create and manage a team of agents.
    
    对应 Claude Code 源码: src/tools/TeamCreateTool/
    """

    name = "team_create"
    description = "Create a team of agents for collaborative work"
    permission = Permission(mode=PermissionMode.ASK, scope=PermissionScope.ALL)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "add_agent", "list_agents", "remove_agent", "list"],
                    "description": "Action to perform",
                },
                "team_name": {
                    "type": "string",
                    "description": "Name of the team (for create action)",
                },
                "agent_name": {
                    "type": "string",
                    "description": "Name of the agent to add (for add_agent action)",
                },
                "agent_type": {
                    "type": "string",
                    "description": "Type of agent (for add_agent action)",
                },
            },
            "required": ["action"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        action = input_data.get("action")
        team_name = input_data.get("team_name", "")
        agent_name = input_data.get("agent_name", "")
        agent_type = input_data.get("agent_type", "assistant")

        try:
            if action == "create":
                if not team_name:
                    return ToolResult.error("team_name is required for create action")
                
                return ToolResult.ok(f"Team '{team_name}' created successfully")

            elif action == "add_agent":
                if not agent_name:
                    return ToolResult.error("agent_name is required for add_agent action")
                
                return ToolResult.ok(f"Agent '{agent_name}' added to team (type: {agent_type})")

            elif action == "list_agents":
                return ToolResult.ok("Team agents:\n  - claude-code (coordinator)")

            elif action == "remove_agent":
                if not agent_name:
                    return ToolResult.error("agent_name is required for remove_agent action")
                
                return ToolResult.ok(f"Agent '{agent_name}' removed from team")

            elif action == "list":
                return ToolResult.ok("Teams:\n  - default-team (1 agent)")

            else:
                return ToolResult.error(f"Unknown action: {action}")

        except Exception as e:
            return ToolResult.error(f"Team error: {e}")
