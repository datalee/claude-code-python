"""
ToolSearchTool - Tool Discovery Tool

对应 Claude Code 源码: src/tools/ToolSearchTool/

功能：
- 搜索可用工具
- 发现新工具
- 延迟工具加载
"""

from __future__ import annotations

from typing import Any, Dict, List

from tool.base import Tool, ToolResult, Permission, PermissionMode, PermissionScope


class ToolSearchTool(Tool):
    """
    Search for available tools.
    
    对应 Claude Code 源码: src/tools/ToolSearchTool/
    
    这是一个"延迟工具发现"机制，允许在需要时才加载工具。
    """

    name = "tool_search"
    description = "Search for available tools"
    permission = Permission(mode=PermissionMode.AUTOMATIC, scope=PermissionScope.READ)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to find tools",
                },
            },
            "required": ["query"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        query = input_data.get("query", "")

        if not query:
            return ToolResult.error("query is required")

        # 从工具注册表搜索
        from tool.registry import get_tool_registry
        registry = get_tool_registry()
        
        all_tools = registry.get_all_tools()
        
        # 简单关键词匹配
        query_lower = query.lower()
        matching_tools = []
        
        for tool in all_tools:
            name_match = query_lower in tool.name.lower()
            desc_match = query_lower in tool.description.lower()
            
            if name_match or desc_match:
                matching_tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "match": "name" if name_match else "description",
                })
        
        if not matching_tools:
            return ToolResult.ok(
                f"No tools found matching: {query}\n\n"
                "Available tools: " + ", ".join(t.name for t in all_tools)
            )
        
        lines = [f"Found {len(matching_tools)} tool(s) matching '{query}':\n"]
        for tool in matching_tools:
            lines.append(f"  - {tool['name']}: {tool['description']}")
        
        return ToolResult.ok("\n".join(lines))
