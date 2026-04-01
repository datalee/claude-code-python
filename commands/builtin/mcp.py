"""
McpCommand - MCP 服务器管理命令

对应 Claude Code 源码: src/commands/mcp/

功能：
- 列出 MCP 服务器
- 添加/移除 MCP 服务器
- 显示 MCP 工具
- MCP 连接状态
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from commands.base import Command, CommandContext, CommandResult


class McpCommand(Command):
    """MCP 服务器管理"""

    name = "mcp"
    description = "Manage MCP (Model Context Protocol) servers"
    aliases = []
    usage = """/mcp
    Manage MCP servers.

Commands:
  /mcp list         - List configured MCP servers
  /mcp tools        - Show available MCP tools
  /mcp status       - Show connection status
  /mcp add <name> <command> - Add MCP server
  /mcp remove <name> - Remove MCP server"""

    def __init__(self) -> None:
        self._mcp_servers: Dict[str, Dict[str, Any]] = {}

    def _load_config(self) -> None:
        """加载 MCP 配置"""
        try:
            from pathlib import Path
            config_file = Path.home() / ".claude" / "mcp.json"
            if config_file.exists():
                import json
                with open(config_file) as f:
                    self._mcp_servers = json.load(f)
        except Exception:
            pass

    def _save_config(self) -> None:
        """保存 MCP 配置"""
        try:
            from pathlib import Path
            config_file = Path.home() / ".claude" / "mcp.json"
            config_file.parent.mkdir(parents=True, exist_ok=True)
            import json
            with open(config_file, "w") as f:
                json.dump(self._mcp_servers, f, indent=2)
        except Exception:
            pass

    async def execute(self, args: List[str], context: CommandContext) -> CommandResult:
        """执行 MCP 命令"""
        try:
            self._load_config()
            
            if not args:
                return CommandResult.ok(self._show_status())
            
            subcmd = args[0].lower()
            
            if subcmd == "list":
                return CommandResult.ok(self._list_servers())
            
            elif subcmd == "tools":
                return CommandResult.ok(self._list_tools())
            
            elif subcmd == "status":
                return CommandResult.ok(self._show_status())
            
            elif subcmd == "add":
                if len(args) < 3:
                    return CommandResult.err("Usage: /mcp add <name> <command>")
                return CommandResult.ok(self._add_server(args[1], args[2]))
            
            elif subcmd == "remove":
                if len(args) < 2:
                    return CommandResult.err("Usage: /mcp remove <name>")
                return CommandResult.ok(self._remove_server(args[1]))
            
            else:
                return CommandResult.err(f"Unknown subcommand: {subcmd}")
        
        except Exception as e:
            return CommandResult.err(f"MCP error: {e}")

    def _list_servers(self) -> str:
        """列出服务器"""
        if not self._mcp_servers:
            return "\nNo MCP servers configured.\n"
        
        lines = ["\n=== MCP Servers ===\n"]
        for name, config in self._mcp_servers.items():
            cmd = config.get("command", "unknown")
            lines.append(f"  {name}: {cmd}")
        
        lines.append("")
        return "\n".join(lines)

    def _list_tools(self) -> str:
        """列出工具"""
        if not self._mcp_servers:
            return "\nNo MCP servers configured.\n"
        
        lines = ["\n=== MCP Tools ===\n"]
        lines.append("  (No tools loaded - MCP requires running server)")
        lines.append("")
        return "\n".join(lines)

    def _show_status(self) -> str:
        """显示状态"""
        lines = ["\n=== MCP Status ===\n"]
        
        if not self._mcp_servers:
            lines.append("  No servers configured")
        else:
            lines.append(f"  {len(self._mcp_servers)} server(s) configured")
            for name in self._mcp_servers:
                lines.append(f"    - {name}")
        
        lines.append("")
        lines.append("  Use /mcp add <name> <command> to add a server")
        lines.append("")
        return "\n".join(lines)

    def _add_server(self, name: str, command: str) -> str:
        """添加服务器"""
        self._mcp_servers[name] = {
            "command": command,
            "enabled": True,
        }
        self._save_config()
        return f"\n  MCP server '{name}' added.\n"

    def _remove_server(self, name: str) -> str:
        """移除服务器"""
        if name in self._mcp_servers:
            del self._mcp_servers[name]
            self._save_config()
            return f"\n  MCP server '{name}' removed.\n"
        return f"\n  MCP server '{name}' not found.\n"
