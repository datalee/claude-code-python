"""
BashTool - Execute shell commands.

Corresponds to: src/tools/BashTool.ts

A tool that executes arbitrary shell commands via subprocess.
Used for running git, npm, build tools, and other shell operations.

Security: Command execution is gated by the permission system.
The PermissionScope controls what types of commands are allowed.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

from tool.base import Permission, PermissionMode, PermissionScope, Tool, ToolResult


def _is_windows() -> bool:
    """Check if we're running on Windows."""
    return sys.platform == "win32" or os.name == "nt"


class BashTool(Tool):
    """
    Execute shell commands in a subprocess.
    
    Corresponds to: src/tools/BashTool.ts
    
    Attributes:
        name: "bash"
        description: "Execute a shell command. Use for git, npm, running scripts, etc."
        permission: Default ASK mode with WRITE scope
        
    Input schema:
        {
            "command": string,        // Required: the shell command to execute
            "cwd": string,            // Optional: working directory
            "timeout_ms": number,    // Optional: timeout in milliseconds
            "environment": object     // Optional: extra environment variables
        }
        
    Output:
        ToolResult with stdout/stderr content on success, error message on failure.
    """

    name = "bash"
    description = (
        "Execute a shell command. Use for git, npm, build tools, and other "
        "shell operations. Returns stdout and stderr as content."
    )

    def __init__(self) -> None:
        self.permission = Permission(
            mode=PermissionMode.ASK,
            scope=PermissionScope.WRITE,
            timeout_ms=60000,  # 60 second default timeout
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": (
                        "The shell command to execute. "
                        "Example: 'git status', 'npm run build', 'python script.py'"
                    ),
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory for the command. Defaults to current directory.",
                },
                "timeout_ms": {
                    "type": "number",
                    "description": "Timeout in milliseconds. Default is 60000 (60 seconds).",
                },
                "environment": {
                    "type": "object",
                    "description": "Additional environment variables to set.",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["command"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """
        Execute the shell command.
        
        Args:
            input_data: Must contain 'command', optionally 'cwd', 'timeout_ms', 'environment'
            
        Returns:
            ToolResult with stdout as content on success,
            error message if command failed or timed out
        """
        command: str = input_data["command"]
        cwd: Optional[str] = input_data.get("cwd")
        timeout_ms: Optional[int] = input_data.get("timeout_ms")
        extra_env: Optional[Dict[str, str]] = input_data.get("environment")

        # Permission check
        allowed, reason = self.check_permission()
        if not allowed:
            return ToolResult.err(reason or "Permission denied")

        # Determine timeout
        timeout_seconds: Optional[float] = None
        if timeout_ms is not None:
            timeout_seconds = timeout_ms / 1000.0
        elif self.permission.timeout_ms is not None:
            timeout_seconds = self.permission.timeout_ms / 1000.0

        # Build environment
        env: Optional[Dict[str, str]] = None
        if extra_env:
            env = {**os.environ, **extra_env}

        # Determine shell and command
        if _is_windows():
            cmd_to_run: List[str] = ["cmd", "/c", command]
            shell_used = "cmd.exe"
        else:
            shell_path = shutil.which("bash")
            cmd_to_run = ["bash", "-c", command] if shell_path else ["sh", "-c", command]
            shell_used = "bash" if shell_path else "sh"

        try:
            # Run command in thread pool to avoid blocking the event loop
            process = await asyncio.create_subprocess_exec(
                *cmd_to_run,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout_seconds
            )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            # Format output
            output_parts: List[str] = []
            if stdout:
                output_parts.append(f"[stdout]\n{stdout}")
            if stderr:
                output_parts.append(f"[stderr]\n{stderr}")

            if process.returncode == 0:
                content = "\n".join(output_parts) if output_parts else "(no output)"
                return ToolResult.ok(
                    content,
                    return_code=process.returncode,
                    shell=shell_used,
                )
            else:
                content = "\n".join(output_parts) if output_parts else f"Command exited with code {process.returncode}"
                return ToolResult.err(
                    content,
                    return_code=process.returncode,
                    shell=shell_used,
                )

        except asyncio.TimeoutError:
            # Try to kill the process
            try:
                process.kill()
            except Exception:
                pass
            return ToolResult.err(
                f"Command timed out after {timeout_seconds}s: {command[:100]}",
                timeout=True,
            )
        except FileNotFoundError:
            return ToolResult.err(f"Shell not found: {shell_used}")
        except PermissionError as e:
            return ToolResult.err(f"Permission denied: {e}")
        except Exception as e:
            return ToolResult.err(f"Command execution failed: {e}")
