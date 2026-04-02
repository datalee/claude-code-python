"""
Memory 模块 - 记忆系统

负责会话上下文的持久化和自动压缩前刷新。
对应 Claude Code 源码: src/memory/*.ts
参考: OpenClaw memory 系统 (memory-core)

架构设计：
1. MemoryBase - 抽象基类，定义记忆接口
2. SessionMemory - 会话记忆，单次对话的生命周期
3. CompactManager - 上下文压缩管理，防止超过 token 限制
4. VectorMemory - 向量记忆搜索（可选，需要 embedding 模型）

记忆文件布局：
- memory/YYYY-MM-DD.md     # 每日日记（自动追加）
- MEMORY.md                # 长期记忆（手动整理）
"""

from __future__ import annotations

from memory.base import MemoryBase, MemoryEntry
from memory.session import SessionMemory
from memory.compact import CompactionManager, CompactionStrategy

__all__ = [
    "MemoryBase",
    "MemoryEntry", 
    "SessionMemory",
    "CompactionManager",
    "CompactionStrategy",
]
