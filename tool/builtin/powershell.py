"""
PowerShellTool - PowerShell Command Execution

对应 Claude Code 源码: src/tools/PowerShellTool/

功能：
- 在 Windows 上执行 PowerShell 命令
- 与 BashTool 类似但专用于 PowerShell
"""

from __future__ import annotations

import asyncio
import subprocess
from typing import Any, Dict, Optional

from tool.base import Tool, ToolResult, Permission, PermissionMode, PermissionScope


class PowerShellTool(Tool):
    """
    Execute PowerShell commands.
    
    对应 Claude Code 源码: src/tools/PowerShellTool/
    """

    name = "powershell"
    description = "Execute PowerShell commands on Windows"
    permission = Permission(mode=PermissionMode.ASK, scope=PermissionScope.ALL)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "PowerShell command to execute",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory for the command",
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds (default: 60)",
                    "default": 60,
                },
            },
            "required": ["command"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        command = input_data.get("command", "")
        cwd = input_data.get("cwd")
        timeout = input_data.get("timeout", 60)

        if not command:
            return ToolResult.error("command is required")

        try:
            # Windows 上执行 PowerShell
            result = await asyncio.create_subprocess_exec(
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                result.communicate(),
                timeout=timeout
            )

            output = stdout.decode("utf-8", errors="replace")
            error_output = stderr.decode("utf-8", errors="replace")

            if result.returncode == 0:
                return ToolResult.ok(output)
            else:
                return ToolResult.error(
                    f"Command failed with exit code {result.returncode}\n{error_output}"
                )

        except asyncio.TimeoutError:
            return ToolResult.error(f"Command timed out after {timeout} seconds")
        except FileNotFoundError:
            return ToolResult.error("PowerShell not found. This tool only works on Windows.")
        except Exception as e:
            return ToolResult.error(f"PowerShell error: {e}")
