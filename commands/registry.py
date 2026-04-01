"""
CommandRegistry - 命令注册表

管理所有可用命令的注册与发现。
对应 Claude Code 源码: src/commands/index.ts
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional, Set

from commands.base import Command, CommandContext, CommandResult


class CommandRegistry:
    """
    命令注册表。
    对应 Claude Code 源码: src/commands/CommandRegistry.ts
    
    功能：
    1. 注册命令（按名称和别名）
    2. 按名称查找命令
    3. 列出所有可用命令
    4. 全局单例访问
    
    示例：
        registry = CommandRegistry()
        
        # 注册命令
        registry.register(NewCommand())
        registry.register(ResetCommand())
        
        # 查找命令
        cmd = registry.get("new")
        
        # 列出所有命令
        for name, cmd in registry.commands.items():
            print(f"{name}: {cmd.description}")
    """

    _instance: Optional["CommandRegistry"] = None
    _initialized: bool = False

    def __new__(cls) -> "CommandRegistry":
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """初始化注册表"""
        if CommandRegistry._initialized:
            return
        
        self.commands: Dict[str, Command] = {}
        """按名称索引的命令字典（包含别名）"""
        
        self.name_to_command: Dict[str, Command] = {}
        """主名称到命令对象的映射"""
        
        self._logger = logging.getLogger("commands.registry")
        
        CommandRegistry._initialized = True

    # -------------------------------------------------------------------------
    # 注册
    # -------------------------------------------------------------------------

    def register(self, command: Command) -> None:
        """
        注册一个命令。
        
        Args:
            command: Command 实例
            
        Raises:
            ValueError: 如果命令名称已存在
        """
        # 注册主名称
        name = command.name.lower()
        if name in self.commands:
            raise ValueError(f"Command already registered: /{name}")
        
        self.commands[name] = command
        self.name_to_command[name] = command
        
        # 注册别名
        for alias in command.aliases:
            alias_lower = alias.lower()
            if alias_lower in self.commands:
                raise ValueError(f"Command alias already registered: /{alias}")
            self.commands[alias_lower] = command
        
        self._logger.debug(f"Registered command: /{name}")

    def register_function(
        self,
        name: str,
        func: Callable[[List[str], CommandContext], CommandResult],
        description: str = "",
        aliases: Optional[List[str]] = None,
        usage: str = "",
    ) -> None:
        """
        注册一个函数作为命令（便捷方法）。
        
        Args:
            name: 命令名称
            func: 异步函数 (args, context) -> CommandResult
            description: 命令描述
            aliases: 命令别名
            usage: 使用说明
        """
        cmd = FunctionCommand(
            name=name,
            func=func,
            description=description,
            aliases=aliases or [],
            usage=usage,
        )
        self.register(cmd)

    def unregister(self, name: str) -> bool:
        """
        注销一个命令。
        
        Args:
            name: 命令名称（不区分大小写）
            
        Returns:
            True 如果成功注销
        """
        name_lower = name.lower()
        
        if name_lower not in self.commands:
            return False
        
        command = self.commands[name_lower]
        
        # 移除主名称
        if self.name_to_command.get(name_lower) is command:
            del self.name_to_command[name_lower]
        
        # 移除别名
        aliases_to_remove = [
            alias for alias, cmd in self.commands.items()
            if cmd is command and alias != name_lower
        ]
        for alias in aliases_to_remove:
            del self.commands[alias]
        
        # 移除主名称条目
        if name_lower in self.commands:
            del self.commands[name_lower]
        
        self._logger.debug(f"Unregistered command: /{name}")
        return True

    # -------------------------------------------------------------------------
    # 查询
    # -------------------------------------------------------------------------

    def get(self, name: str) -> Optional[Command]:
        """
        按名称查找命令。
        
        Args:
            name: 命令名称（支持别名）
            
        Returns:
            Command 实例，或 None
        """
        return self.commands.get(name.lower())

    def get_primary(self, name: str) -> Optional[Command]:
        """
        按名称查找主命令（不包括别名）。
        
        Args:
            name: 命令名称
            
        Returns:
            Command 实例，或 None
        """
        return self.name_to_command.get(name.lower())

    def list_all(self) -> List[Command]:
        """
        列出所有主命令（不含别名）。
        
        Returns:
            Command 实例列表
        """
        return list(self.name_to_command.values())

    def list_names(self) -> List[str]:
        """
        列出所有命令名称（不含别名）。
        
        Returns:
            命令名称列表
        """
        return list(self.name_to_command.keys())

    def help_text(self) -> str:
        """
        生成所有命令的帮助文本。
        
        Returns:
            格式化的帮助字符串
        """
        lines = ["Available commands:", ""]
        
        for name, cmd in sorted(self.name_to_command.items()):
            lines.append(f"  /{name:<12} {cmd.description}")
            for alias in cmd.aliases:
                lines.append(f"  /{alias:<12} (alias for /{name})")
        
        return "\n".join(lines)

    def match(self, input_str: str) -> Optional[Command]:
        """
        匹配输入字符串到命令。
        
        Args:
            input_str: 用户输入（可能带斜杠）
            
        Returns:
            匹配的命令，或 None
        """
        if not input_str:
            return None
        
        # 提取命令名称
        cmd = input_str.strip().lstrip("/").split()[0].lower()
        
        if not cmd:
            return None
        
        return self.commands.get(cmd)


class FunctionCommand(Command):
    """
    函数包装命令。
    将普通函数包装为 Command 对象。
    
    示例：
        async def my_command(args, context):
            return CommandResult.ok("Done!")
        
        cmd = FunctionCommand(
            name="hello",
            func=my_command,
            description="Say hello",
        )
    """

    def __init__(
        self,
        name: str,
        func: Callable[[List[str], CommandContext], CommandResult],
        description: str = "",
        aliases: Optional[List[str]] = None,
        usage: str = "",
    ) -> None:
        self.name = name
        self.description = description
        self.aliases = aliases or []
        self.usage = usage
        self._func = func

    async def execute(self, args: List[str], context: CommandContext) -> CommandResult:
        """执行函数"""
        return await self._func(args, context)


# =============================================================================
# 全局单例访问函数
# =============================================================================

_registry: Optional[CommandRegistry] = None


def get_command_registry() -> CommandRegistry:
    """获取全局命令注册表单例"""
    global _registry
    if _registry is None:
        _registry = CommandRegistry()
    return _registry


def register_builtin_commands() -> None:
    """注册所有内置命令（便捷函数）"""
    from commands.builtin import (
        NewCommand,
        ResetCommand,
        QuitCommand,
        ModelCommand,
        CostCommand,
        HistoryCommand,
        StatusCommand,
        HelpCommand,
        ClearCommand,
    )
    
    registry = get_command_registry()
    
    registry.register(NewCommand())
    registry.register(ResetCommand())
    registry.register(QuitCommand())
    registry.register(ModelCommand())
    registry.register(CostCommand())
    registry.register(HistoryCommand())
    registry.register(StatusCommand())
    registry.register(HelpCommand())
    registry.register(ClearCommand())
