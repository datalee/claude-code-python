"""
ConfigCommand - 配置管理命令

对应 Claude Code 源码: src/commands/config/

功能：
- 查看当前配置
- 设置配置项
- 重置配置
- 配置文件路径
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from commands.base import Command, CommandContext, CommandResult


# 默认配置
DEFAULT_CONFIG = {
    "version": "1.0.0",
    "model": "claude-sonnet-4-20250514",
    "permission_mode": "safe",
    "memory_enabled": True,
    "hooks_enabled": True,
    "auto_compact": True,
    "compact_threshold_tokens": 100000,
    "max_tokens": 4096,
    "temperature": 1.0,
}


class ConfigCommand(Command):
    """配置管理"""

    name = "config"
    description = "View and modify configuration"
    aliases = ["settings"]
    usage = """/config [key] [value]
    View or modify configuration.

Commands:
  /config            - Show all config
  /config <key>      - Show specific config value
  /config <key> <value> - Set config value
  /config reset       - Reset to defaults
  /config path        - Show config file path

Examples:
  /config model
  /config model claude-opus-4-20250514
  /config permission_mode ask"""

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
                self._config = DEFAULT_CONFIG.copy()
        else:
            self._config = DEFAULT_CONFIG.copy()

    def _save_config(self) -> None:
        """保存配置"""
        self._config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_file, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)

    def _get_all(self) -> str:
        """获取所有配置"""
        lines = ["\n=== Configuration ===\n"]
        lines.append(f"Config file: {self._config_file}\n")
        
        for key in sorted(self._config.keys()):
            value = self._config[key]
            lines.append(f"  {key}: {value}")
        
        lines.append("")
        return "\n".join(lines)

    def _get_value(self, key: str) -> Optional[str]:
        """获取指定配置"""
        if key not in self._config:
            return None
        return str(self._config[key])

    def _set_value(self, key: str, value_str: str) -> str:
        """设置配置"""
        # 类型处理
        if key in self._config:
            current = self._config[key]
            if isinstance(current, bool):
                value = value_str.lower() in ("true", "1", "yes", "on")
            elif isinstance(current, int):
                value = int(value_str)
            elif isinstance(current, float):
                value = float(value_str)
            else:
                value = value_str
        else:
            # 未知的配置项，尝试智能推断类型
            if value_str.lower() in ("true", "false"):
                value = value_str.lower() == "true"
            elif value_str.isdigit():
                value = int(value_str)
            elif value_str.replace(".", "", 1).isdigit():
                value = float(value_str)
            else:
                value = value_str

        self._config[key] = value
        self._save_config()
        return f"  {key}: {value} (updated)"

    async def execute(self, args: List[str], context: CommandContext) -> CommandResult:
        """执行配置命令"""
        try:
            # 无参数 - 显示所有配置
            if not args:
                return CommandResult.ok(self._get_all())

            # 单参数 - 可能是 key 或特殊命令
            if len(args) == 1:
                arg = args[0].lower()

                # 特殊命令
                if arg == "reset":
                    self._config = DEFAULT_CONFIG.copy()
                    self._save_config()
                    return CommandResult.ok("Config reset to defaults.")

                if arg == "path":
                    return CommandResult.ok(f"Config file: {self._config_file}")

                if arg == "help":
                    return CommandResult.ok(self.usage)

                # 尝试获取配置值
                value = self._get_value(arg)
                if value is not None:
                    return CommandResult.ok(f"  {arg}: {value}")
                else:
                    return CommandResult.err(f"Unknown config key: {arg}")

            # 两个参数 - key value
            if len(args) == 2:
                key, value = args[0], args[1]
                result = self._set_value(key, value)
                return CommandResult.ok(result)

            # 太多参数
            return CommandResult.err("Too many arguments. Usage: /config [key] [value]")

        except Exception as e:
            return CommandResult.err(f"Config error: {e}")
