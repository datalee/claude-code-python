"""
Compact Module - Conversation Context Compaction

对话上下文压缩模块，用于减少 token 使用量。
对应 Claude Code 源码: src/compact/*.ts

功能：
- 自动检测上下文膨胀
- 压缩旧消息
- 生成摘要
- 保留关键信息
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Message:
    """消息"""
    role: str  # user, assistant, system
    content: str
    timestamp: float = field(default_factory=time.time)
    tokens: int = 0


@dataclass
class CompactionResult:
    """压缩结果"""
    original_count: int
    original_tokens: int
    compacted_count: int
    compacted_tokens: int
    summary: str
    removed_messages: List[int]  # 被移除的消息索引


class Compactor:
    """
    上下文压缩器。
    """

    def __init__(
        self,
        threshold_tokens: int = 100000,
        max_messages: int = 1000,
        summarizer: Optional[Callable[[List[Message]], str]] = None,
    ) -> None:
        self.threshold_tokens = threshold_tokens
        self.max_messages = max_messages
        self.summarizer = summarizer or self._default_summarizer

    def _default_summarizer(self, messages: List[Message]) -> str:
        """默认摘要生成器"""
        if not messages:
            return ""
        
        # 简单摘要：提取关键信息
        total_length = sum(len(m.content) for m in messages)
        avg_length = total_length // len(messages) if messages else 0
        
        lines = [
            f"Conversation summary ({len(messages)} messages, ~{total_length} chars):",
            "",
        ]
        
        # 按角色分组统计
        by_role: Dict[str, List[Message]] = {}
        for msg in messages:
            if msg.role not in by_role:
                by_role[msg.role] = []
            by_role[msg.role].append(msg)
        
        for role, msgs in by_role.items():
            lines.append(f"- {role}: {len(msgs)} messages")
        
        return "\n".join(lines)

    def should_compact(self, messages: List[Message]) -> bool:
        """检查是否需要压缩"""
        total_tokens = sum(m.tokens for m in messages)
        return total_tokens > self.threshold_tokens or len(messages) > self.max_messages

    async def compact(self, messages: List[Message]) -> CompactionResult:
        """
        压缩消息列表。
        
        Args:
            messages: 消息列表
            
        Returns:
            CompactionResult: 压缩结果
        """
        original_count = len(messages)
        original_tokens = sum(m.tokens for m in messages)

        if not messages:
            return CompactionResult(
                original_count=0,
                original_tokens=0,
                compacted_count=0,
                compacted_tokens=0,
                summary="",
                removed_messages=[],
            )

        # 保留策略：
        # 1. 保留最新的 N 条消息
        # 2. 保留系统消息
        # 3. 压缩中间的消息

        KEEP_RECENT = 10  # 保留最近 10 条
        KEEP_FIRST = 1    # 保留第一条（通常是 system）

        if len(messages) <= KEEP_RECENT + KEEP_FIRST:
            # 消息不多，不需要压缩
            return CompactionResult(
                original_count=original_count,
                original_tokens=original_tokens,
                compacted_count=original_count,
                compacted_tokens=original_tokens,
                summary="No compaction needed - not enough messages",
                removed_messages=[],
            )

        # 确定保留的消息
        keep_indices = set()

        # 保留第一条（通常是 system）
        keep_indices.add(0)

        # 保留最近的 N 条
        for i in range(len(messages) - KEEP_RECENT, len(messages)):
            keep_indices.add(i)

        # 被压缩的消息
        compact_indices = [i for i in range(len(messages)) if i not in keep_indices]
        compact_messages = [messages[i] for i in compact_indices]

        # 生成摘要
        summary = await self._summarize(compact_messages)

        # 构建压缩后的消息列表
        compacted = [messages[0]]  # system

        # 添加摘要消息
        summary_msg = Message(
            role="system",
            content=f"[Compressed previous {len(compact_messages)} messages]\n{summary}",
            timestamp=time.time(),
            tokens=len(summary) // 4,  # 粗略估算
        )
        compacted.append(summary_msg)

        # 添加最近的消息
        for i in range(len(messages) - KEEP_RECENT, len(messages)):
            compacted.append(messages[i])

        compacted_tokens = sum(m.tokens for m in compacted)

        return CompactionResult(
            original_count=original_count,
            original_tokens=original_tokens,
            compacted_count=len(compacted),
            compacted_tokens=compacted_tokens,
            summary=summary,
            removed_messages=compact_indices,
        )

    async def _summarize(self, messages: List[Message]) -> str:
        """生成摘要"""
        return self.summarizer(messages)


class SmartCompactor(Compactor):
    """
    智能压缩器。
    
    使用 AI 模型生成更好的摘要。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model

    async def _summarize(self, messages: List[Message]) -> str:
        """使用 AI 生成摘要"""
        if not self.api_key:
            return super()._summarize(messages)

        # 构建摘要请求
        prompt = self._build_summary_prompt(messages)

        try:
            # 调用 API 生成摘要
            # 实际实现需要调用 Anthropic API
            return await self._call_anthropic(prompt)

        except Exception as e:
            # 失败时使用默认摘要
            return super()._summarize(messages)

    def _build_summary_prompt(self, messages: List[Message]) -> str:
        """构建摘要提示"""
        lines = [
            "Please summarize the following conversation concisely.",
            "Focus on:",
            "1. Main topics discussed",
            "2. Key decisions made",
            "3. Important facts or information shared",
            "4. Any tasks or action items mentioned",
            "",
            "Conversation:",
        ]

        for msg in messages:
            lines.append(f"\n[{msg.role}]: {msg.content[:500]}")  # 截断长消息

        return "\n".join(lines)

    async def _call_anthropic(self, prompt: str) -> str:
        """调用 Anthropic API"""
        # 这个需要实际实现 API 调用
        # 简化实现
        return "[Summary of conversation - API call not implemented]"


# ============================================================================
# 辅助函数
# ============================================================================

import os


def create_compactor(
    mode: str = "simple",
    **kwargs,
) -> Compactor:
    """
    创建压缩器。
    
    Args:
        mode: 压缩模式 ("simple" 或 "smart")
        **kwargs: 传递给压缩器的参数
        
    Returns:
        Compactor 实例
    """
    if mode == "smart":
        return SmartCompactor(**kwargs)
    return Compactor(**kwargs)


__all__ = [
    "Compactor",
    "SmartCompactor",
    "CompactionResult",
    "Message",
    "create_compactor",
]
