"""
FileReadTool - Read file contents.

Corresponds to: src/tools/FileReadTool.ts (conceptually similar to ReadTool)

A read-only tool for reading file contents.
Permission is automatically set to READ scope with AUTOMATIC mode.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

from tool.base import Permission, PermissionMode, PermissionScope, Tool, ToolResult


class FileReadTool(Tool):
    """
    Read the contents of a file.
    
    Corresponds to: src/tools/FileReadTool.ts (concept)
    
    Permission: READ scope, AUTOMATIC mode (no confirmation needed).
    
    Input schema:
        {
            "path": string,           // Required: file path to read
            "limit": number,           // Optional: max number of lines to read
            "offset": number,         // Optional: line number to start from (1-indexed)
            "line_numbers": boolean,  // Optional: show line numbers (default false)
        }
        
    Output:
        ToolResult with file contents, or error if file doesn't exist / can't be read.
    """

    name = "read"
    description = (
        "Read the contents of a file. Returns the full file content or a limited range. "
        "Use this to examine code files, configuration, logs, etc."
    )

    def __init__(self) -> None:
        self.permission = Permission(
            mode=PermissionMode.AUTOMATIC,
            scope=PermissionScope.READ,
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read. Can be absolute or relative.",
                },
                "limit": {
                    "type": "number",
                    "description": "Maximum number of lines to read. Omit for full file.",
                },
                "offset": {
                    "type": "number",
                    "description": "Line number to start reading from (1-indexed). Default: 1",
                },
                "line_numbers": {
                    "type": "boolean",
                    "description": "Whether to include line numbers in the output. Default: false",
                },
            },
            "required": ["path"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """
        Read file contents.
        
        Args:
            input_data: Must contain 'path', optionally 'limit', 'offset', 'line_numbers'
            
        Returns:
            ToolResult with file content, or error message
        """
        path_str: str = input_data["path"]
        limit: Optional[int] = input_data.get("limit")
        offset: int = input_data.get("offset", 1)
        line_numbers: bool = input_data.get("line_numbers", False)

        # Permission check
        allowed, reason = self.check_permission()
        if not allowed:
            return ToolResult.err(reason or "Permission denied")

        # Resolve path
        path = Path(path_str).expanduser().resolve()

        if not path.exists():
            return ToolResult.err(f"File not found: {path}")

        if not path.is_file():
            return ToolResult.err(f"Not a file: {path}")

        try:
            # Read file content
            content = await asyncio.to_thread(self._read_file, path, offset, limit, line_numbers)
            return ToolResult.ok(content, path=str(path), lines_read=len(content.splitlines()))
        except UnicodeDecodeError:
            return ToolResult.err(f"File is not text (binary): {path}")
        except PermissionError:
            return ToolResult.err(f"Permission denied: {path}")
        except Exception as e:
            return ToolResult.err(f"Failed to read file: {e}")

    def _read_file(
        self, path: Path, offset: int, limit: Optional[int], line_numbers: bool
    ) -> str:
        """
        Read file with line range and optional line numbers.
        
        Args:
            path: File path
            offset: 1-indexed start line
            limit: Max lines to read (None = all)
            line_numbers: Whether to prefix each line with line number
            
        Returns:
            Formatted file content as string
        """
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        # Apply offset (convert 1-indexed to 0-indexed)
        start = max(0, offset - 1)
        end = None if limit is None else start + limit
        selected_lines = lines[start:end]

        if line_numbers:
            result_lines: List[str] = []
            for i, line in enumerate(selected_lines, start=start + 1):
                result_lines.append(f"{i:6}  {line.rstrip()}")
            return "\n".join(result_lines)
        else:
            return "".join(selected_lines).rstrip("\n")
