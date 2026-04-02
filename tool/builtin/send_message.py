"""
SendMessageTool - Send Message Tool

对应 Claude Code 源码: src/tools/SendMessageTool/

功能：
- 向其他 agent 发送消息
- 跨 agent 通信
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from tool.base import Tool, ToolResult, Permission, PermissionMode, PermissionScope


class SendMessageTool(Tool):
    """
    Send a message to another agent or user.
    
    对应 Claude Code 源码: src/tools/SendMessageTool/
    """

    name = "send_message"
    description = "Send a message to another agent or user"
    permission = Permission(mode=PermissionMode.ASK, scope=PermissionScope.ALL)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message to send",
                },
                "to": {
                    "type": "string",
                    "description": "Recipient identifier (agent ID or user ID)",
                },
                "channel": {
                    "type": "string",
                    "description": "Communication channel (e.g., 'slack', 'discord', 'feishu')",
                },
            },
            "required": ["message", "to"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        message = input_data.get("message", "")
        to = input_data.get("to", "")
        channel = input_data.get("channel", "")

        if not message:
            return ToolResult.error("message is required")
        
        if not to:
            return ToolResult.error("to is required")

        try:
            # 这个工具需要实际的消息传递后端
            # 这里提供框架实现，具体实现依赖外部服务
            return ToolResult.ok(
                content=f"Message queued to {to}",
                metadata={
                    "to": to,
                    "channel": channel or "default",
                    "message": message,
                    "queued": True,
                }
            )
        
        except Exception as e:
            return ToolResult.error(f"Failed to send message: {e}")
