"""
Hook Builtin - 内置钩子实现

提供三个内置钩子：
1. SessionMemoryHook - /new 命令时保存会话上下文
2. CommandLoggerHook - 记录所有命令事件
3. BootMdHook - Gateway 启动时运行 BOOT.md
"""

from __future__ import annotations

from hook.builtin.session_memory import SessionMemoryHook
from hook.builtin.command_logger import CommandLoggerHook
from hook.builtin.boot_md import BootMdHook

__all__ = [
    "SessionMemoryHook",
    "CommandLoggerHook",
    "BootMdHook",
]
