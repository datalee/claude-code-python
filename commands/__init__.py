"""
Commands Module - 命令系统

提供完整的命令框架，包括内置命令和命令注册表。
对应 Claude Code 源码: src/commands/*.ts

核心组件：
- Command: 命令抽象基类
- CommandContext: 命令执行上下文
- CommandResult: 命令执行结果
- CommandRegistry: 命令注册表

内置命令：
- /new - 开始新会话
- /reset - 重置当前会话
- /quit - 退出 REPL
- /model - 切换模型
- /cost - 查看成本
- /history - 查看历史
- /status - 查看状态
- /help - 显示帮助
- /clear - 清屏

示例：
    from commands import get_command_registry, register_builtin_commands
    
    # 初始化注册表
    registry = get_command_registry()
    register_builtin_commands()
    
    # 查找并执行命令
    cmd = registry.get("new")
    result = await cmd.execute([], context)
"""

from __future__ import annotations

from commands.base import Command, CommandContext, CommandResult
from commands.registry import (
    CommandRegistry,
    FunctionCommand,
    get_command_registry,
    register_builtin_commands,
)

__all__ = [
    # 核心类
    "Command",
    "CommandContext",
    "CommandResult",
    "CommandRegistry",
    "FunctionCommand",
    # 注册函数
    "get_command_registry",
    "register_builtin_commands",
]
