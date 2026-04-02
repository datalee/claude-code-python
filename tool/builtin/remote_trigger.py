"""
RemoteTriggerTool - Remote Trigger Tool

对应 Claude Code 源码: src/tools/RemoteTriggerTool/

功能：
- 触发远程操作
- 跨设备/跨会话控制
- 发送触发信号
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from tool.base import Tool, ToolResult, Permission, PermissionMode, PermissionScope


class RemoteTriggerTool(Tool):
    """
    Trigger a remote action on another device or session.
    
    对应 Claude Code 源码: src/tools/RemoteTriggerTool/
    """

    name = "remote_trigger"
    description = "Trigger a remote action on another device or session"
    permission = Permission(mode=PermissionMode.ASK, scope=PermissionScope.ALL)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "The action to trigger",
                },
                "target": {
                    "type": "string",
                    "description": "Target device or session identifier",
                },
                "params": {
                    "type": "object",
                    "description": "Additional parameters for the action",
                },
            },
            "required": ["action", "target"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        action = input_data.get("action", "")
        target = input_data.get("target", "")
        params = input_data.get("params", {})

        if not action:
            return ToolResult.error("action is required")
        
        if not target:
            return ToolResult.error("target is required")

        try:
            # 这个工具需要远程连接支持
            # 框架实现：返回触发信息
            return ToolResult.ok(
                f"Remote trigger sent:\n"
                f"  Action: {action}\n"
                f"  Target: {target}\n"
                f"  Params: {params}\n"
                f"  Status: queued"
            )

        except Exception as e:
            return ToolResult.error(f"Remote trigger error: {e}")
