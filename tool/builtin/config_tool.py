"""
ConfigTool - Configuration Management Tool

对应 Claude Code 源码: src/tools/ConfigTool/

功能：
- 读取配置项
- 写入配置项
- 列出所有配置
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from tool.base import Tool, ToolResult, Permission, PermissionMode, PermissionScope


class ConfigTool(Tool):
    """
    Read and write configuration values.
    
    对应 Claude Code 源码: src/tools/ConfigTool/
    """

    name = "config"
    description = "Read or write configuration values"
    permission = Permission(mode=PermissionMode.ASK, scope=PermissionScope.ALL)

    def __init__(self) -> None:
        self._config_file = Path.home() / ".claude" / "config.json"
        self._config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """加载配置"""
        if self._config_file.exists():
            try:
                with open(self._config_file, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
            except Exception:
                self._config = {}
        else:
            self._config = {}

    def _save_config(self) -> None:
        """保存配置"""
        self._config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_file, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get", "set", "list"],
                    "description": "Action to perform: get (read value), set (write value), list (show all)",
                },
                "key": {
                    "type": "string",
                    "description": "Configuration key to read or write",
                },
                "value": {
                    "type": "string",
                    "description": "Value to write (only for set action)",
                },
            },
            "required": ["action"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        action = input_data.get("action")
        key = input_data.get("key")
        value = input_data.get("value")

        try:
            self._load_config()

            if action == "get":
                if not key:
                    return ToolResult.error("key is required for get action")
                
                if key not in self._config:
                    return ToolResult.error(f"Config key not found: {key}")
                
                return ToolResult.ok(f"{key} = {self._config[key]}")

            elif action == "set":
                if not key:
                    return ToolResult.error("key is required for set action")
                if value is None:
                    return ToolResult.error("value is required for set action")
                
                # 智能类型转换
                current = self._config.get(key)
                if isinstance(current, bool):
                    parsed_value = value.lower() in ("true", "1", "yes", "on")
                elif isinstance(current, int):
                    parsed_value = int(value)
                elif isinstance(current, float):
                    parsed_value = float(value)
                else:
                    parsed_value = value
                
                self._config[key] = parsed_value
                self._save_config()
                
                return ToolResult.ok(f"{key} = {parsed_value} (saved)")

            elif action == "list":
                lines = ["Current configuration:"]
                for k, v in sorted(self._config.items()):
                    lines.append(f"  {k} = {v}")
                
                return ToolResult.ok("\n".join(lines))

            else:
                return ToolResult.error(f"Unknown action: {action}")

        except Exception as e:
            return ToolResult.error(f"Config error: {e}")
