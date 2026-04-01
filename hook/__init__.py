"""
Hook 模块 - 事件驱动的自动化钩子

在特定事件发生时自动执行预定义操作。
对应 Claude Code 源码: src/hooks/*.ts
参考: OpenClaw hooks 系统

架构设计：
1. HookBase - 钩子抽象基类
2. HookEvent - 事件类型定义
3. HookRegistry - 钩子注册表
4. 内置钩子：
   - SessionMemoryHook: /new 命令时保存会话上下文
   - CommandLoggerHook: 记录所有命令事件
   - BootMdHook: Gateway 启动时运行 BOOT.md

事件类型：
- gateway:startup  - Gateway 启动时
- gateway:shutdown - Gateway 关闭时
- command:new      - 执行 /new 命令
- command:reset    - 执行 /reset 命令
- command:quit     - 执行 /quit 命令
- session:start    - 会话开始
- session:end      - 会话结束
- compaction:before - 上下文压缩前
- compaction:after - 上下文压缩后
"""

from __future__ import annotations

from hook.base import Hook, HookConfig, HookResult
from hook.events import HookEvent, EventType
from hook.registry import HookRegistry, get_hook_registry

__all__ = [
    "Hook",
    "HookConfig",
    "HookResult",
    "HookEvent",
    "EventType",
    "HookRegistry",
    "get_hook_registry",
]
