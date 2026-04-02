"""
Compact Manager - 上下文压缩管理

当会话接近 token 限制时，自动触发压缩机制：
1. 识别可压缩的记忆条目
2. 生成压缩摘要
3. 释放 token 空间

对应 Claude Code 源码: src/memory/CompactManager.ts
参考: OpenClaw compaction.memoryFlush 配置
"""

from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import tiktoken


class CompactionStrategy(Enum):
    """
    压缩策略。
    对应 Claude Code 源码: src/memory/CompactionStrategy
    """
    TRUNCATE = "truncate"           # 直接截断（简单粗暴）
    SUMMARIZE = "summarize"         # 生成摘要（智能）
    SELECTIVE = "selective"         # 选择性保留（精细）


@dataclass
class CompactionCandidate:
    """
    压缩候选项。
    代表一条可以被压缩的记忆条目。
    
    Attributes:
        memory_id: 记忆 ID
        content: 记忆内容
        token_count: token 数量
        priority: 记忆优先级
        age_seconds: 记忆年龄（秒）
        can_delete: 是否可以删除
        can_summarize: 是否可以摘要
    """
    memory_id: str
    content: str
    token_count: int
    priority: str  # high/medium/low
    age_seconds: float
    can_delete: bool = True
    can_summarize: bool = True
    summary: Optional[str] = None  # 压缩后的摘要


@dataclass
class CompactionResult:
    """
    压缩结果。
    
    Attributes:
        original_tokens: 压缩前 token 数
        compressed_tokens: 压缩后 token 数
        freed_tokens: 释放的 token 数
        deleted_entries: 删除的记忆 ID 列表
        summarized_entries: 被摘要的记忆 ID 列表
        strategy: 使用的压缩策略
        duration_ms: 压缩耗时（毫秒）
    """
    original_tokens: int
    compressed_tokens: int
    freed_tokens: int
    deleted_entries: List[str] = field(default_factory=list)
    summarized_entries: List[str] = field(default_factory=list)
    strategy: CompactionStrategy = CompactionStrategy.TRUNCATE
    duration_ms: float = 0

    @property
    def compression_ratio(self) -> float:
        """压缩率（0-1，越高压缩越多）"""
        if self.original_tokens == 0:
            return 0
        return self.freed_tokens / self.original_tokens


class CompactionManager:
    """
    上下文压缩管理器。
    对应 Claude Code 源码: src/memory/CompactManager.ts
    参考: OpenClaw agents.defaults.compaction.memoryFlush
    
    职责：
    1. 监控 token 使用量
    2. 触发压缩阈值时执行压缩
    3. 选择合适的压缩策略
    4. 追踪压缩历史
    
    配置参数：
    - reserve_tokens_floor: 保留 token 下限（默认 20000）
    - soft_threshold_tokens: 软阈值（达到此值触发警告）
    - compaction_threshold: 强制压缩阈值
    
    示例：
        manager = CompactionManager(
            max_tokens=200000,
            reserve_tokens_floor=20000,
            soft_threshold=40000,
        )
        
        # 检查是否需要压缩
        if manager.should_compact(current_tokens):
            result = await manager.compact(memories, strategy='summarize')
    """

    DEFAULT_RESERVE_FLOOR = 20_000   # 保留 token 下限
    DEFAULT_SOFT_THRESHOLD = 40_000  # 软阈值（警告）
    DEFAULT_HARD_THRESHOLD = 180_000 # 硬阈值（强制压缩）

    def __init__(
        self,
        max_tokens: int = 200_000,
        reserve_tokens_floor: int = DEFAULT_RESERVE_FLOOR,
        soft_threshold: int = DEFAULT_SOFT_THRESHOLD,
        compaction_threshold: int = DEFAULT_HARD_THRESHOLD,
        encoder: Optional[Any] = None,
    ) -> None:
        """
        初始化压缩管理器。
        
        Args:
            max_tokens: 最大 token 上下文窗口
            reserve_tokens_floor: 保留 token 下限（不被压缩）
            soft_threshold: 软阈值（建议压缩）
            compaction_threshold: 强制压缩阈值
            encoder: tiktoken 编码器（None 则创建）
        """
        self.max_tokens = max_tokens
        self.reserve_tokens_floor = reserve_tokens_floor
        self.soft_threshold = soft_threshold
        self.compaction_threshold = compaction_threshold
        
        # Token 计数器
        self._encoder = encoder
        if self._encoder is None:
            try:
                self._encoder = tiktoken.get_encoding("cl100k_base")
            except Exception:
                pass  # 回退到字符估算
        
        # 压缩历史
        self._compaction_history: List[CompactionResult] = []

    def count_tokens(self, text: str) -> int:
        """
        计算 token 数量。
        
        Args:
            text: 要计算的文本
            
        Returns:
            token 数量
        """
        if self._encoder:
            return len(self._encoder.encode(text))
        return len(text) // 4  # 备用估算

    def should_compact(self, current_tokens: int) -> tuple[bool, str]:
        """
        检查是否应该压缩。
        
        Args:
            current_tokens: 当前 token 数
            
        Returns:
            (是否需要压缩, 原因)
        """
        available = self.max_tokens - current_tokens
        
        if current_tokens >= self.compaction_threshold:
            return True, f"硬阈值触发: {current_tokens}/{self.compaction_threshold}"
        
        if current_tokens >= self.soft_threshold:
            return True, f"软阈值触发: {current_tokens}/{self.soft_threshold}"
        
        if available < self.reserve_tokens_floor:
            return True, f"可用空间不足: {available} < {self.reserve_tokens_floor}"
        
        return False, "无需压缩"

    def get_compaction_targets(
        self,
        memories: List[Any],  # List[MemoryEntry]
        current_tokens: int,
        target_freed_tokens: Optional[int] = None,
    ) -> List[CompactionCandidate]:
        """
        获取需要压缩的记忆候选项。
        
        Args:
            memories: 记忆条目列表
            current_tokens: 当前 token 数
            target_freed_tokens: 目标释放 token 数
            
        Returns:
            按优先级排序的压缩候选项列表
        """
        candidates = []
        
        # 计算需要释放多少 token
        if target_freed_tokens is None:
            target_freed_tokens = current_tokens - (self.max_tokens - self.reserve_tokens_floor)
        
        for memory in memories:
            # 跳过高优先级记忆
            if hasattr(memory, 'priority') and memory.priority == 'high':
                continue
            
            token_count = self.count_tokens(
                memory.content if hasattr(memory, 'content') else str(memory)
            )
            
            # 根据策略决定是否可以删除
            can_delete = self._should_delete(memory)
            
            candidate = CompactionCandidate(
                memory_id=getattr(memory, 'id', str(memory)),
                content=getattr(memory, 'content', str(memory)),
                token_count=token_count,
                priority=getattr(memory, 'priority', 'medium'),
                age_seconds=time.time() - getattr(memory, 'created_at', time.time()),
                can_delete=can_delete,
                can_summarize=True,
            )
            candidates.append(candidate)
        
        # 按优先级和年龄排序
        # 策略：优先删除低优先级 + 旧记忆
        def sort_key(c: CompactionCandidate) -> tuple:
            priority_order = {"low": 0, "medium": 1, "high": 2}
            priority = priority_order.get(c.priority, 1)
            return (priority, -c.age_seconds)  # 低优先级、旧的先删
        
        candidates.sort(key=sort_key)
        return candidates
    
    def _should_delete(self, memory: Any) -> bool:
        """
        根据策略决定记忆是否应该被删除。
        
        删除策略：
        1. 长期记忆(LONG_TERM)不删除
        2. 新记忆(< 1小时)不删除
        3. 最近访问的记忆不删除
        4. 高优先级记忆不删除
        
        Args:
            memory: 记忆条目
            
        Returns:
            是否可以删除
        """
        import time as time_module
        
        # 1. 检查记忆类型
        memory_type = getattr(memory, 'type', None)
        if memory_type is not None:
            # LONG_TERM 类型不删除
            if hasattr(memory_type, 'value') and memory_type.value == 'long_term':
                return False
        
        # 2. 检查优先级
        priority = getattr(memory, 'priority', 'medium')
        if priority == 'high':
            return False
        
        # 3. 检查年龄（少于1小时的记忆不删除）
        created_at = getattr(memory, 'created_at', time_module.time())
        age_seconds = time_module.time() - created_at
        if age_seconds < 3600:  # 1小时
            return False
        
        # 4. 检查最近访问
        updated_at = getattr(memory, 'updated_at', created_at)
        if updated_at > created_at and (time_module.time() - updated_at) < 86400:  # 24小时内更新过
            return False
        
        # 满足所有条件，可以删除
        return True
        """
        获取需要压缩的记忆候选项。
        
        Args:
            memories: 记忆条目列表
            current_tokens: 当前 token 数
            target_freed_tokens: 目标释放 token 数
            
        Returns:
            按优先级排序的压缩候选项列表
        """
        candidates = []
        
        # 计算需要释放多少 token
        if target_freed_tokens is None:
            target_freed_tokens = current_tokens - (self.max_tokens - self.reserve_tokens_floor)
        
        for memory in memories:
            # 跳过高优先级记忆
            if hasattr(memory, 'priority') and memory.priority == 'high':
                continue
            
            token_count = self.count_tokens(
                memory.content if hasattr(memory, 'content') else str(memory)
            )
            
            # 根据策略决定是否可以删除
            can_delete = self._should_delete(memory)
            
            candidate = CompactionCandidate(
                memory_id=getattr(memory, 'id', str(memory)),
                content=getattr(memory, 'content', str(memory)),
                token_count=token_count,
                priority=getattr(memory, 'priority', 'medium'),
                age_seconds=time.time() - getattr(memory, 'created_at', time.time()),
                can_delete=can_delete,
                can_summarize=True,
            )
            candidates.append(candidate)
        
        # 按优先级和年龄排序
        # 策略：优先删除低优先级 + 旧记忆
        def sort_key(c: CompactionCandidate) -> tuple:
            priority_order = {"low": 0, "medium": 1, "high": 2}
            priority = priority_order.get(c.priority, 1)
            return (priority, -c.age_seconds)  # 低优先级、旧的先删
        
        candidates.sort(key=sort_key)
        
        return candidates

    async def compact(
        self,
        memories: List[Any],
        strategy: CompactionStrategy = CompactionStrategy.SUMMARIZE,
        current_tokens: Optional[int] = None,
    ) -> CompactionResult:
        """
        执行压缩。
        
        Args:
            memories: 要压缩的记忆列表
            strategy: 压缩策略
            current_tokens: 当前 token 数（None 则自动计算）
            
        Returns:
            压缩结果
        """
        start_time = time.time()
        
        if current_tokens is None:
            current_tokens = sum(
                self.count_tokens(getattr(m, 'content', str(m)))
                for m in memories
            )
        
        candidates = self.get_compaction_targets(
            memories, current_tokens
        )
        
        deleted = []
        summarized = []
        
        if strategy == CompactionStrategy.TRUNCATE:
            # 简单截断策略：删除最低优先级的记忆
            deleted = await self._compact_by_deletion(candidates)
        
        elif strategy == CompactionStrategy.SUMMARIZE:
            # 摘要策略：保留摘要，删除原文
            summarized = await self._compact_by_summarize(candidates)
        
        elif strategy == CompactionStrategy.SELECTIVE:
            # 选择性策略：智能组合
            deleted, summarized = await self._compact_selective(candidates)
        
        # 计算结果
        freed_tokens = sum(
            c.token_count for c in candidates
            if c.memory_id in deleted or c.memory_id in summarized
        )
        
        result = CompactionResult(
            original_tokens=current_tokens,
            compressed_tokens=current_tokens - freed_tokens,
            freed_tokens=freed_tokens,
            deleted_entries=deleted,
            summarized_entries=summarized,
            strategy=strategy,
            duration_ms=(time.time() - start_time) * 1000,
        )
        
        self._compaction_history.append(result)
        
        return result

    async def _compact_by_deletion(
        self,
        candidates: List[CompactionCandidate],
    ) -> List[str]:
        """通过删除进行压缩"""
        deleted = []
        
        for c in candidates:
            if c.can_delete:
                deleted.append(c.memory_id)
        
        return deleted

    async def _compact_by_summarize(
        self,
        candidates: List[CompactionCandidate],
    ) -> List[str]:
        """通过摘要进行压缩"""
        summarized = []
        
        # 获取 API key
        import os
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        api_base_url = os.environ.get("ANTHROPIC_API_BASE_URL", "https://api.anthropic.com/v1")
        
        for c in candidates:
            if c.can_summarize:
                if api_key:
                    # 使用 LLM 生成摘要
                    c.summary = await self._generate_summary_with_llm(c.content, api_key, api_base_url)
                else:
                    # 回退到简单截断
                    c.summary = c.content[:200] + "..." if len(c.content) > 200 else c.content
                summarized.append(c.memory_id)
        
        return summarized

    async def _generate_summary_with_llm(self, content: str, api_key: str, api_base_url: str) -> str:
        """调用 LLM 生成摘要（支持 Anthropic 和 OpenAI 兼容格式）"""
        import httpx
        
        prompt = f"""Please summarize the following text concisely, keeping the key information:

{content[:4000]}

Summary:"""
        
        # 检测是否 OpenAI 兼容模式
        is_openai = "volces" in api_base_url or "openai" in api_base_url or "ark." in api_base_url
        
        if is_openai:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            request_body = {
                "model": "claude-sonnet-4-20250514",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 512,
                "temperature": 0.3,
            }
            # Volcengine 需要 /v1 前缀
            if "/v1" not in api_base_url:
                url = f"{api_base_url}/v1/chat/completions"
            else:
                url = f"{api_base_url}/chat/completions"
        else:
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            request_body = {
                "model": "claude-sonnet-4-20250514",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 512,
                "temperature": 0.3,
            }
            url = f"{api_base_url}/messages"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=request_body)
                
                if response.status_code == 200:
                    data = response.json()
                    if is_openai:
                        if data.get("choices"):
                            return data["choices"][0].get("message", {}).get("content", "")
                    else:
                        for block in data.get("content", []):
                            if block.get("type") == "text":
                                return block.get("text", "")
        except Exception:
            pass
        
        # 失败时回退到截断
        return content[:200] + "..." if len(content) > 200 else content

    async def _compact_selective(
        self,
        candidates: List[CompactionCandidate],
    ) -> tuple[List[str], List[str]]:
        """选择性压缩：结合删除和摘要"""
        deleted = []
        summarized = []
        
        for c in candidates:
            if c.can_delete and c.priority == 'low':
                deleted.append(c.memory_id)
            elif c.can_summarize:
                summarized.append(c.memory_id)
        
        return deleted, summarized

    def get_compaction_stats(self) -> Dict[str, Any]:
        """
        获取压缩统计。
        
        Returns:
            统计信息字典
        """
        if not self._compaction_history:
            return {
                "total_compactions": 0,
                "total_freed_tokens": 0,
                "average_ratio": 0,
            }
        
        total = len(self._compaction_history)
        total_freed = sum(r.freed_tokens for r in self._compaction_history)
        avg_ratio = sum(r.compression_ratio for r in self._compaction_history) / total
        
        return {
            "total_compactions": total,
            "total_freed_tokens": total_freed,
            "average_compression_ratio": avg_ratio,
            "last_compaction": self._compaction_history[-1].to_dict() if self._compaction_history else None,
        }
