"""
ListMcpResourcesTool - List MCP Resources Tool

对应 Claude Code 源码: src/tools/ListMcpResourcesTool/

功能：
- 列出 MCP 服务器资源
- 显示可用资源
"""

from __future__ import annotations

from typing import Any, Dict, List

from tool.base import Tool, ToolResult, Permission, PermissionMode, PermissionScope


class ListMcpResourcesTool(Tool):
    """
    List available MCP (Model Context Protocol) resources.
    
    对应 Claude Code 源码: src/tools/ListMcpResourcesTool/
    """

    name = "list_mcp_resources"
    description = "List available MCP resources"
    permission = Permission(mode=PermissionMode.AUTOMATIC, scope=PermissionScope.READ)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "server": {
                    "type": "string",
                    "description": "MCP server name to list resources for (optional)",
                },
            },
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        server = input_data.get("server", "")

        try:
            # MCP 资源列表
            # 这里返回框架级别的信息，实际资源由 MCP 服务器提供
            if server:
                return ToolResult.ok(
                    f"MCP Resources for '{server}':\n"
                    f"  (No MCP server configured - use /mcp add to configure)"
                )
            
            return ToolResult.ok(
                "MCP Servers:\n"
                "  (No MCP servers configured)\n\n"
                "Use /mcp add <name> <command> to configure an MCP server."
            )

        except Exception as e:
            return ToolResult.error(f"List MCP resources error: {e}")
