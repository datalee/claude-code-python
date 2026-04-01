"""
GlobTool - Find files matching glob patterns.

Corresponds to: src/tools/GlobTool.ts

A read-only tool for finding files using glob patterns.
Useful for discovering files in a project (e.g., "find all *.py files").
"""

from __future__ import annotations

import asyncio
import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional

from tool.base import Permission, PermissionMode, PermissionScope, Tool, ToolResult


class GlobTool(Tool):
    """
    Find files matching glob patterns.
    
    Corresponds to: src/tools/GlobTool.ts
    
    Permission: READ scope, AUTOMATIC mode.
    
    Input schema:
        {
            "pattern": string,    // Required: glob pattern (e.g., "**/*.py", "src/**/*.ts")
            "base_dir": string,  // Optional: directory to search in (default: current dir)
            "max_results": number // Optional: maximum files to return (default: 100)
        }
        
    Output:
        ToolResult with list of matching file paths, one per line.
    """

    name = "glob"
    description = (
        "Find files matching a glob pattern. "
        "Use patterns like '**/*.py' to find all Python files, "
        "'**/*.ts' for TypeScript, '**/package.json' for project files, etc."
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
                "pattern": {
                    "type": "string",
                    "description": (
                        "Glob pattern to match files. "
                        "Examples: '**/*.py' (all Python files), "
                        "'src/**/*.ts' (TypeScript in src), "
                        "'**/package.json' (all package.json files)"
                    ),
                },
                "base_dir": {
                    "type": "string",
                    "description": "Base directory to search in. Defaults to current directory.",
                },
                "max_results": {
                    "type": "number",
                    "description": "Maximum number of results to return. Default: 100",
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """
        Find files matching a glob pattern.
        
        Args:
            input_data: Must contain 'pattern', optionally 'base_dir', 'max_results'
            
        Returns:
            ToolResult with newline-separated list of matching paths
        """
        pattern: str = input_data["pattern"]
        base_dir_str: Optional[str] = input_data.get("base_dir")
        max_results: int = input_data.get("max_results", 100)

        # Permission check
        allowed, reason = self.check_permission()
        if not allowed:
            return ToolResult.err(reason or "Permission denied")

        # Resolve base directory
        if base_dir_str:
            base_dir = Path(base_dir_str).expanduser().resolve()
        else:
            base_dir = Path.cwd()

        if not base_dir.exists():
            return ToolResult.err(f"Directory not found: {base_dir}")

        try:
            matches = await asyncio.to_thread(self._glob, base_dir, pattern, max_results)
            
            if not matches:
                return ToolResult.ok(
                    "(no files matched)",
                    pattern=pattern,
                    base_dir=str(base_dir),
                    count=0,
                )
            
            return ToolResult.ok(
                "\n".join(matches),
                pattern=pattern,
                base_dir=str(base_dir),
                count=len(matches),
            )
        except Exception as e:
            return ToolResult.err(f"Glob failed: {e}")

    def _glob(self, base_dir: Path, pattern: str, max_results: int) -> List[str]:
        """
        Perform glob matching.
        
        Uses pathlib.Path.rglob for recursive patterns (/**/).
        For complex patterns, falls back to fnmatch.
        """
        # Handle recursive patterns
        if "**" in pattern:
            matches_gen = base_dir.glob(pattern)
            matches = list(matches_gen)[:max_results]
        else:
            # Non-recursive glob
            matches_gen = base_dir.glob(pattern)
            matches = list(matches_gen)[:max_results]

        # Filter to files only, return as strings
        result: List[str] = []
        for match in matches:
            if match.is_file():
                # Return relative path from base_dir
                try:
                    rel_path = match.relative_to(base_dir)
                    result.append(str(rel_path))
                except ValueError:
                    result.append(str(match))

        return result
