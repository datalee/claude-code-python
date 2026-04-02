"""
FileEditTool - Create and edit files.

Corresponds to: src/tools/FileEditTool.ts

Provides file creation and editing capabilities.
Supports:
- Creating new files with content
- Replacing text in existing files (search and replace)
- Appending to files
- Creating directories

Security: WRITE scope, requires ASK permission (user must confirm).
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from tool.base import Permission, PermissionMode, PermissionScope, Tool, ToolResult


class EditMode(Enum):
    """File edit operation types."""
    CREATE = "create"
    REPLACE = "replace"
    APPEND = "append"
    WRITE = "write"  # Overwrite entire file


@dataclass
class EditOperation:
    """Represents a single edit operation."""
    old_text: Optional[str] = None  # Text to find (None for create/append)
    new_text: Optional[str] = None   # Replacement text
    mode: EditMode = EditMode.WRITE


class FileEditTool(Tool):
    """
    Create or edit files with search-and-replace operations.
    
    Corresponds to: src/tools/FileEditTool.ts
    
    Permission: WRITE scope, ASK mode (requires user confirmation).
    
    Input schema:
        {
            "path": string,            // Required: file path to edit
            "operation": string,       // "create" | "replace" | "append" | "write"
            "new_text": string,       // Text to write / replace with
            "old_text": string,       // Text to find (for replace mode)
            "create_dirs": boolean,   // Auto-create parent directories (default: false)
        }
        
    Design notes:
    - The "replace" operation uses exact text matching
    - For regex replacement, old_text is treated as a regex pattern when re_search=true
    - This implements the same "Read -> Edit -> Write" pattern as Claude Code's TS version
    """

    name = "edit"
    description = (
        "Create a new file or edit an existing file using search-and-replace. "
        "For replacement, provide the exact old_text to find and new_text to replace it. "
        "Use 'create' to create a new file, 'write' to overwrite entirely."
    )

    def __init__(self) -> None:
        self.permission = Permission(
            mode=PermissionMode.ASK,
            scope=PermissionScope.WRITE,
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to create or edit.",
                },
                "operation": {
                    "type": "string",
                    "enum": ["create", "replace", "append", "write", "undo", "multi_replace"],
                    "description": (
                        "Edit operation type: "
                        "'create' (new file), 'replace' (search and replace text), "
                        "'append' (add to end of file), 'write' (overwrite entire file), "
                        "'undo' (undo last edit), 'multi_replace' (batch replace)"
                    ),
                },
                "new_text": {
                    "type": "string",
                    "description": "Text to write / replace with.",
                },
                "old_text": {
                    "type": "string",
                    "description": (
                        "Text to find for replacement. "
                        "Must match exactly (including whitespace) for 'replace' mode."
                    ),
                },
                "replacements": {
                    "type": "array",
                    "description": "List of {old, new} pairs for multi_replace operation.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "old": {"type": "string"},
                            "new": {"type": "string"},
                        },
                        "required": ["old"],
                    },
                },
                "create_dirs": {
                    "type": "boolean",
                    "description": "Create parent directories if they don't exist. Default: false",
                },
                "re_search": {
                    "type": "boolean",
                    "description": "Treat old_text as a regex pattern. Default: false",
                },
            },
            "required": ["path", "operation"],
            "allOf": [
                {
                    "if": {"properties": {"operation": {"const": "replace"}}},
                    "then": {"required": ["old_text", "new_text"]},
                },
                {
                    "if": {"properties": {"operation": {"const": "write"}}},
                    "then": {"required": ["new_text"]},
                },
                {
                    "if": {"properties": {"operation": {"const": "multi_replace"}}},
                    "then": {"required": ["replacements"]},
                },
            ],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """
        Execute file edit operation.
        
        Args:
            input_data: Contains path, operation, new_text, old_text, etc.
            
        Returns:
            ToolResult with success message or error
        """
        path_str: str = input_data["path"]
        operation: str = input_data["operation"]
        new_text: Optional[str] = input_data.get("new_text", "")
        old_text: Optional[str] = input_data.get("old_text")
        create_dirs: bool = input_data.get("create_dirs", False)
        re_search: bool = input_data.get("re_search", False)

        # Permission check
        allowed, reason = self.check_permission()
        if not allowed:
            return ToolResult.err(reason or "Permission denied")

        path = Path(path_str).expanduser().resolve()

        # Create parent directories if requested
        if create_dirs and not path.parent.exists():
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                return ToolResult.err(f"Failed to create directories: {e}")

        try:
            # Handle special operations
            if operation == "undo":
                return await asyncio.to_thread(self.undo, str(path))
            elif operation == "multi_replace":
                replacements = input_data.get("replacements", [])
                return await asyncio.to_thread(self.multi_replace, str(path), replacements)
            
            # Normal edit operations
            result_text = await asyncio.to_thread(
                self._edit_file, path, operation, new_text, old_text, re_search
            )
            return ToolResult.ok(
                result_text,
                path=str(path),
                operation=operation,
                size_bytes=path.stat().st_size if path.exists() else len(new_text or ""),
            )
        except FileNotFoundError:
            return ToolResult.err(f"File not found: {path} (did you mean to use operation='create'?)")
        except PermissionError:
            return ToolResult.err(f"Permission denied: {path}")
        except ValueError as e:
            return ToolResult.err(f"Edit failed: {e}")
        except Exception as e:
            return ToolResult.err(f"Edit failed: {e}")

    def _edit_file(
        self,
        path: Path,
        operation: str,
        new_text: Optional[str],
        old_text: Optional[str],
        re_search: bool,
    ) -> str:
        """
        Perform the actual file edit operation.
        
        Args:
            path: File path
            operation: One of create, replace, append, write
            new_text: New text for write/replace/create
            old_text: Text to find for replace
            re_search: Whether to treat old_text as regex
            
        Returns:
            Success message describing what was done
        """
        mode = EditMode(operation)

        if mode == EditMode.CREATE:
            return self._create_file(path, new_text or "")
        elif mode == EditMode.WRITE:
            return self._write_file(path, new_text or "")
        elif mode == EditMode.APPEND:
            return self._append_file(path, new_text or "")
        elif mode == EditMode.REPLACE:
            if old_text is None:
                raise ValueError("old_text is required for replace operation")
            return self._replace_in_file(path, old_text, new_text or "", re_search)
        else:
            raise ValueError(f"Unknown edit mode: {operation}")

    def _create_file(self, path: Path, content: str) -> str:
        """Create a new file with content."""
        if path.exists():
            raise FileExistsError(f"File already exists: {path}. Use 'replace' or 'write' to modify it.")
        # Save None as original_content to indicate file didn't exist (for undo)
        self._save_for_undo(str(path), "create", None)
        path.write_text(content, encoding="utf-8")
        return f"Created file: {path}"

    def _write_file(self, path: Path, content: str) -> str:
        """Overwrite file with new content."""
        # Save original content for undo
        original = path.read_text(encoding="utf-8") if path.exists() else None
        self._save_for_undo(str(path), "write", original)
        path.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} characters to: {path}"

    def _append_file(self, path: Path, content: str) -> str:
        """Append content to end of file."""
        # Save original for undo
        original = path.read_text(encoding="utf-8") if path.exists() else None
        self._save_for_undo(str(path), "append", original)
        
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            content = existing + "\n" + content
        path.write_text(content, encoding="utf-8")
        return f"Appended {len(content)} characters to: {path}"

    def _replace_in_file(
        self, path: Path, old_text: str, new_text: str, re_search: bool
    ) -> str:
        """
        Find and replace text in a file.
        
        Args:
            path: File to edit
            old_text: Text to find (exact match or regex if re_search=True)
            new_text: Replacement text
            re_search: Whether old_text is a regex pattern
            
        Returns:
            Success message
            
        Raises:
            FileNotFoundError: File doesn't exist
            ValueError: old_text not found (or pattern doesn't match)
        """
        content = path.read_text(encoding="utf-8")
        
        # Save original for undo
        self._save_for_undo(str(path), "replace", content)

        if re_search:
            new_content, count = re.subn(old_text, new_text, content, count=1)
        else:
            if old_text not in content:
                raise ValueError(
                    f"Text not found in file: {old_text[:100]!r}..."
                )
            new_content = content.replace(old_text, new_text, 1)

        path.write_text(new_content, encoding="utf-8")
        return f"Replaced 1 occurrence in: {path}"

    def _save_for_undo(self, path: str, operation: str, original_content: Optional[str]) -> None:
        """Save file state for undo before modification."""
        if path not in _edit_history:
            _edit_history[path] = []
        _edit_history[path].append({
            "operation": operation,
            "original_content": original_content,
        })
        # Limit history to last 50 operations per file
        if len(_edit_history[path]) > 50:
            _edit_history[path].pop(0)

    def undo(self, path: str) -> ToolResult:
        """
        Undo the last edit operation on a file.
        
        Args:
            path: Path to the file to undo
            
        Returns:
            ToolResult with undo status
        """
        path_obj = Path(path)
        
        # Check if we have history for this file
        if path not in _edit_history:
            return ToolResult.err(f"No edit history found for: {path}")
        
        history = _edit_history[path]
        if not history:
            return ToolResult.err(f"No more operations to undo for: {path}")
        
        # Pop the last operation
        last_backup = history.pop()
        
        # Restore the previous version
        try:
            if last_backup["original_content"] is None:
                # File didn't exist before, delete it
                if path_obj.exists():
                    path_obj.unlink()
                message = f"Deleted file (was newly created): {path}"
            else:
                # Restore original content
                path_obj.write_text(last_backup["original_content"], encoding="utf-8")
                message = f"Undid {last_backup['operation']} operation on: {path}"
            
            # Clean up if no more history
            if not history:
                del _edit_history[path]
            
            return ToolResult(success=True, content=message)
        except Exception as e:
            return ToolResult.err(f"Undo failed: {e}")
    
    def multi_replace(self, path: str, replacements: List[Dict[str, str]]) -> ToolResult:
        """
        Perform multiple search-replace operations in a single file.
        
        Args:
            path: Path to the file
            replacements: List of {"old": "...", "new": "..."} dicts
            
        Returns:
            ToolResult with replacement count
        """
        path_obj = Path(path)
        
        if not path_obj.exists():
            return ToolResult.err(f"File not found: {path}")
        
        # Save original for undo (single undo point for batch)
        original_content = path_obj.read_text(encoding="utf-8")
        self._save_for_undo(path, "multi_replace", original_content)
        
        content = original_content
        total_count = 0
        
        for repl in replacements:
            old_text = repl.get("old", "")
            new_text = repl.get("new", "")
            
            if not old_text:
                continue
            
            if old_text in content:
                content = content.replace(old_text, new_text, 1)
                total_count += 1
        
        if total_count == 0:
            return ToolResult.err("No replacements made (patterns not found)")
        
        path_obj.write_text(content, encoding="utf-8")
        return ToolResult(success=True, content=f"Replaced {total_count} occurrence(s) in: {path}")


# Module-level edit history: path -> list of backups
_edit_history: Dict[str, List[Dict[str, Any]]] = {}
