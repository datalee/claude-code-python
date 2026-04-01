"""
TodoWriteTool - Todo Write Tool

对应 Claude Code 源码: src/tools/TodoWriteTool/

功能：
- 创建 todo 项
- 写入 todo 列表
- 管理 todo 状态
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from tool.base import Tool, ToolResult, Permission, PermissionMode, PermissionScope


class TodoWriteTool(Tool):
    """
    Write or update a todo item.
    
    对应 Claude Code 源码: src/tools/TodoWriteTool/
    """

    name = "todo_write"
    description = "Write or update a todo item"
    permission = Permission(mode=PermissionMode.ASK, scope=PermissionScope.WRITE)

    def __init__(self) -> None:
        self._todo_file = Path.home() / ".claude" / "todos.json"

    def _load_todos(self) -> List[Dict[str, Any]]:
        """加载 todos"""
        if self._todo_file.exists():
            try:
                with open(self._todo_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_todos(self, todos: List[Dict[str, Any]]) -> None:
        """保存 todos"""
        self._todo_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._todo_file, "w", encoding="utf-8") as f:
            json.dump(todos, f, indent=2, ensure_ascii=False)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "done", "remove", "list"],
                    "description": "Action to perform",
                },
                "text": {
                    "type": "string",
                    "description": "Todo text (for add action)",
                },
                "id": {
                    "type": "integer",
                    "description": "Todo ID (for done/remove actions)",
                },
            },
            "required": ["action"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        action = input_data.get("action")
        text = input_data.get("text", "")
        todo_id = input_data.get("id")

        try:
            todos = self._load_todos()

            if action == "add":
                if not text:
                    return ToolResult.error("text is required for add action")
                
                new_id = max([t["id"] for t in todos], default=0) + 1
                todo = {
                    "id": new_id,
                    "text": text,
                    "status": "pending",
                    "created_at": time.time(),
                }
                todos.append(todo)
                self._save_todos(todos)
                return ToolResult.ok(f"Added todo #{new_id}: {text}")

            elif action == "done":
                if todo_id is None:
                    return ToolResult.error("id is required for done action")
                
                for todo in todos:
                    if todo["id"] == todo_id:
                        todo["status"] = "done"
                        todo["completed_at"] = time.time()
                        self._save_todos(todos)
                        return ToolResult.ok(f"Todo #{todo_id} marked as done")
                
                return ToolResult.error(f"Todo #{todo_id} not found")

            elif action == "remove":
                if todo_id is None:
                    return ToolResult.error("id is required for remove action")
                
                original_len = len(todos)
                todos = [t for t in todos if t["id"] != todo_id]
                
                if len(todos) < original_len:
                    self._save_todos(todos)
                    return ToolResult.ok(f"Todo #{todo_id} removed")
                
                return ToolResult.error(f"Todo #{todo_id} not found")

            elif action == "list":
                if not todos:
                    return ToolResult.ok("No todos. Add one with /todo add <text>")
                
                lines = ["\n=== Todos ===\n"]
                for todo in todos:
                    checkbox = "[x]" if todo["status"] == "done" else "[ ]"
                    lines.append(f"  {checkbox} #{todo['id']}: {todo['text']}")
                
                lines.append("")
                return ToolResult.ok("\n".join(lines))

            else:
                return ToolResult.error(f"Unknown action: {action}")

        except Exception as e:
            return ToolResult.error(f"Todo error: {e}")
