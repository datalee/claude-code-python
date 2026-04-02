"""
NotebookEditTool - Jupyter Notebook Editor

对应 Claude Code 源码: src/tools/NotebookEditTool/

功能：
- 编辑 Jupyter notebook
- 修改 cell 内容
- 添加/删除 cells
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from tool.base import Tool, ToolResult, Permission, PermissionMode, PermissionScope


class NotebookEditTool(Tool):
    """
    Edit a Jupyter notebook (.ipynb file).
    
    对应 Claude Code 源码: src/tools/NotebookEditTool/
    """

    name = "notebook_edit"
    description = "Edit a Jupyter notebook"
    permission = Permission(mode=PermissionMode.ASK, scope=PermissionScope.WRITE)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the notebook file (.ipynb)",
                },
                "action": {
                    "type": "string",
                    "enum": ["add_code", "add_markdown", "delete_cell", "update_cell"],
                    "description": "Action to perform",
                },
                "cell_index": {
                    "type": "integer",
                    "description": "Cell index (for delete/update actions)",
                },
                "content": {
                    "type": "string",
                    "description": "Cell content (for add/update actions)",
                },
            },
            "required": ["path", "action"],
        }

    def _load_notebook(self, path: Path) -> Dict[str, Any]:
        """Load notebook."""
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_notebook(self, path: Path, nb: Dict[str, Any]) -> None:
        """Save notebook."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(nb, f, indent=2, ensure_ascii=False)

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        path_str = input_data.get("path", "")
        action = input_data.get("action")
        cell_index = input_data.get("cell_index")
        content = input_data.get("content", "")

        if not path_str:
            return ToolResult.error("path is required")

        path = Path(path_str)

        if not path.exists():
            return ToolResult.error(f"Notebook not found: {path}")

        if path.suffix != ".ipynb":
            return ToolResult.error("File must be a .ipynb notebook")

        try:
            nb = self._load_notebook(path)

            if action == "add_code":
                new_cell = {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [content],
                }
                nb["cells"].append(new_cell)
                cell_num = len(nb["cells"]) - 1
                self._save_notebook(path, nb)
                return ToolResult.ok(f"Added code cell #{cell_num}")

            elif action == "add_markdown":
                new_cell = {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [content],
                }
                nb["cells"].append(new_cell)
                cell_num = len(nb["cells"]) - 1
                self._save_notebook(path, nb)
                return ToolResult.ok(f"Added markdown cell #{cell_num}")

            elif action == "delete_cell":
                if cell_index is None:
                    return ToolResult.error("cell_index is required for delete_cell")
                
                if cell_index < 0 or cell_index >= len(nb["cells"]):
                    return ToolResult.error(f"Cell index out of range: {cell_index}")
                
                del nb["cells"][cell_index]
                self._save_notebook(path, nb)
                return ToolResult.ok(f"Deleted cell #{cell_index}")

            elif action == "update_cell":
                if cell_index is None:
                    return ToolResult.error("cell_index is required for update_cell")
                
                if cell_index < 0 or cell_index >= len(nb["cells"]):
                    return ToolResult.error(f"Cell index out of range: {cell_index}")
                
                nb["cells"][cell_index]["source"] = [content]
                self._save_notebook(path, nb)
                return ToolResult.ok(f"Updated cell #{cell_index}")

            else:
                return ToolResult.error(f"Unknown action: {action}")

        except Exception as e:
            return ToolResult.error(f"Notebook edit error: {e}")
