"""
ReadMcpResourceTool - Read MCP Resource Tool

对应 Claude Code 源码: src/tools/ReadMcpResourceTool/

功能：
- 读取 MCP 资源内容
- 获取特定资源数据
"""

from __future__ import annotations

from typing import Any, Dict

from tool.base import Tool, ToolResult, Permission, PermissionMode, PermissionScope


class ReadMcpResourceTool(Tool):
    """
    Read a specific MCP resource.
    
    对应 Claude Code 源码: src/tools/ReadMcpResourceTool/
    """

    name = "read_mcp_resource"
    description = "Read a specific MCP resource"
    permission = Permission(mode=PermissionMode.ASK, scope=PermissionScope.READ)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "uri": {
                    "type": "string",
                    "description": "URI of the MCP resource to read",
                },
            },
            "required": ["uri"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        uri = input_data.get("uri", "")

        if not uri:
            return ToolResult.error("uri is required")

        try:
            # MCP 资源读取需要实际连接 MCP 服务器
            # 这里返回框架级别响应
            if uri.startswith("mcp://"):
                return ToolResult.ok(
                    f"MCP Resource: {uri}\n"
                    f"  (Requires active MCP server connection)"
                )
            
            return ToolResult.error(f"Invalid MCP URI: {uri}")

        except Exception as e:
            return ToolResult.error(f"Read MCP resource error: {e}")
