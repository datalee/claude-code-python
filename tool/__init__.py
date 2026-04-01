"""
Claude Code Python - Tool System

This module provides the core Tool abstraction and registry for the Claude Code agent.
"""

from tool.base import (
    Tool,
    ToolResult,
    Permission,
    PermissionScope,
    PermissionMode,
)
from tool.registry import ToolRegistry, get_tool_registry

__all__ = [
    "Tool",
    "ToolResult",
    "Permission",
    "PermissionScope",
    "PermissionMode",
    "ToolRegistry",
    "get_tool_registry",
]
