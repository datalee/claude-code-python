"""
Session Memory - 会话记忆管理

管理单次对话的生命周期，包括：
- 会话开始时加载相关记忆
- 会话结束时保存上下文到记忆
- 自动关联相关记忆条目

对应 Claude Code 源码: src/memory/SessionMemory.ts
参考: OpenClaw session-memory hook
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from memory.base import MemoryBase, MemoryEntry, MemoryType, MemoryPriority


@dataclass
class SessionContext:
    """
    会话上下文快照。
    用于在会话结束时保存到记忆。
    
    Attributes:
        session_id: 会话唯一 ID
        start_time: 会话开始时间
        end_time: 会话结束时间
        user_messages: 用户消息数
        assistant_messages: 助手消息数
        tool_calls: 工具调用数
        summary: 会话摘要（LLM 生成）
        decisions: 关键决策列表
        preferences: 用户偏好列表
        errors: 错误列表
    """
    session_id: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    user_messages: int = 0
    assistant_messages: int = 0
    tool_calls: int = 0
    summary: str = ""
    decisions: List[str] = field(default_factory=list)
    preferences: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "user_messages": self.user_messages,
            "assistant_messages": self.assistant_messages,
            "tool_calls": self.tool_calls,
            "summary": self.summary,
            "decisions": self.decisions,
            "preferences": self.preferences,
            "errors": self.errors,
        }

    def duration_seconds(self) -> float:
        """会话持续时间（秒）"""
        end = self.end_time or time.time()
        return end - self.start_time


class SessionMemory:
    """
    会话记忆管理器。
    对应 Claude Code 源码: src/memory/SessionMemory.ts
    参考: OpenClaw session-memory hook
    
    职责：
    1. 管理单次对话的生命周期
    2. 追踪会话统计（消息数、工具调用等）
    3. 会话结束时自动保存摘要到记忆
    4. 提供上下文加载接口
    
    设计原则：
    - 会话记忆是临时的，存储在内存中
    - 结束时会话摘要写入每日日记
    - 重要决策和偏好会写入长期记忆
    
    示例：
        session = SessionMemory(memory_backend)
        await session.start(user_id="user123")
        
        # 对话中追踪统计
        await session.track_message(role="user")
        await session.track_tool_call(tool_name="read")
        await session.add_decision("使用 Python 而非 JavaScript")
        
        # 会话结束
        await session.end(summary="完成了 API 重构...")
    """

    def __init__(
        self,
        memory: MemoryBase,
        session_file_dir: Optional[Path] = None,
    ) -> None:
        """
        初始化会话记忆管理器。
        
        Args:
            memory: 底层记忆存储
            session_file_dir: 会话文件存储目录（用于调试）
        """
        self.memory = memory
        self.session_file_dir = session_file_dir
        
        # 当前会话状态
        self._current_session: Optional[SessionContext] = None
        self._message_buffer: List[Dict[str, Any]] = []

    async def start(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SessionContext:
        """
        开始新会话。
        
        Args:
            session_id: 会话 ID（None 则自动生成）
            user_id: 用户 ID
            metadata: 额外元数据
            
        Returns:
            新创建的会话上下文
        """
        import uuid
        
        self._current_session = SessionContext(
            session_id=session_id or f"session_{uuid.uuid4().hex[:12]}",
        )
        self._message_buffer = []
        
        if metadata:
            self._current_session.metadata.update(metadata)
        
        # 加载相关记忆到上下文
        await self._load_relevant_memories(user_id)
        
        return self._current_session

    async def end(
        self,
        summary: str = "",
        save_to_memory: bool = True,
    ) -> Optional[MemoryEntry]:
        """
        结束当前会话。
        
        Args:
            summary: 会话摘要（可由 LLM 生成）
            save_to_memory: 是否保存到记忆
            
        Returns:
            创建的记忆条目
        """
        if self._current_session is None:
            return None
        
        # 更新结束时间
        self._current_session.end_time = time.time()
        self._current_session.summary = summary
        
        if save_to_memory:
            # 保存会话摘要到每日日记
            entry = await self._save_session_summary()
            
            # 重要决策写入长期记忆
            if self._current_session.decisions:
                await self._save_decisions_to_long_term()
            
            return entry
        
        return None

    async def track_message(
        self,
        role: str,
        content: str = "",
        tool_calls: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        追踪一条消息。
        
        Args:
            role: 角色（user/assistant/system）
            content: 消息内容
            tool_calls: 工具调用列表
        """
        if self._current_session is None:
            return
        
        # 记录消息
        self._message_buffer.append({
            "role": role,
            "content": content[:500] if content else "",  # 截断存储
            "tool_calls": tool_calls,
            "timestamp": time.time(),
        })
        
        # 更新统计
        if role == "user":
            self._current_session.user_messages += 1
        elif role == "assistant":
            self._current_session.assistant_messages += 1
            if tool_calls:
                self._current_session.tool_calls += len(tool_calls)

    async def track_tool_call(
        self,
        tool_name: str,
        input_data: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """
        追踪一次工具调用。
        
        Args:
            tool_name: 工具名称
            input_data: 输入参数
            success: 是否成功
            error: 错误信息
        """
        if self._current_session is None:
            return
        
        self._current_session.tool_calls += 1
        
        if not success and error:
            self._current_session.errors.append(f"{tool_name}: {error}")

    async def add_decision(
        self,
        decision: str,
        reason: Optional[str] = None,
        importance: str = "medium",
    ) -> None:
        """
        记录一个关键决策。
        
        Args:
            decision: 决策内容
            reason: 决策原因
            importance: 重要程度（high/medium/low）
        """
        if self._current_session is None:
            return
        
        decision_text = decision
        if reason:
            decision_text += f"（原因: {reason}）"
        
        self._current_session.decisions.append(decision_text)
        
        # 高重要度决策立即写入长期记忆
        if importance == "high":
            await self._save_decision_to_long_term(decision_text)

    async def add_preference(
        self,
        preference: str,
        category: str = "general",
    ) -> None:
        """
        记录用户偏好。
        
        Args:
            preference: 偏好内容
            category: 类别（coding/style/communication 等）
        """
        if self._current_session is None:
            return
        
        pref_text = f"[{category}] {preference}"
        self._current_session.preferences.append(pref_text)

    def get_current_session(self) -> Optional[SessionContext]:
        """获取当前会话上下文"""
        return self._current_session

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取当前会话统计。
        
        Returns:
            统计信息字典
        """
        if self._current_session is None:
            return {}
        
        return {
            "session_id": self._current_session.session_id,
            "duration": self._current_session.duration_seconds(),
            "user_messages": self._current_session.user_messages,
            "assistant_messages": self._current_session.assistant_messages,
            "tool_calls": self._current_session.tool_calls,
            "decisions": len(self._current_session.decisions),
            "errors": len(self._current_session.errors),
        }

    # -------------------------------------------------------------------------
    # 私有方法
    # -------------------------------------------------------------------------

    async def _load_relevant_memories(self, user_id: Optional[str]) -> None:
        """
        加载相关记忆到会话上下文。
        
        策略：
        1. 加载今天的日记
        2. 加载用户偏好
        3. 加载最近的决策上下文
        """
        # TODO: 实现向量搜索或关键词匹配
        # 目前简单加载今天日记
        today_entries = await self.memory.list_daily()
        
        # 过滤相关条目
        relevant = [
            e for e in today_entries
            if e.type == MemoryType.DAILY
        ]
        
        return relevant

    async def _save_session_summary(self) -> MemoryEntry:
        """将会话摘要保存到每日日记"""
        session = self._current_session
        if session is None:
            raise RuntimeError("No active session")
        
        # 生成摘要 Markdown
        lines = [
            f"## 会话摘要: {session.session_id}",
            f"**时间**: {datetime.fromtimestamp(session.start_time).strftime('%H:%M')} - "
            f"{datetime.fromtimestamp(session.end_time or time.time()).strftime('%H:%M')}",
            f"**持续**: {session.duration_seconds():.1f} 秒",
            "",
            f"**统计**: {session.user_messages} 条用户消息, "
            f"{session.assistant_messages} 条助手消息, "
            f"{session.tool_calls} 次工具调用",
            "",
        ]
        
        if session.summary:
            lines.append(f"**摘要**: {session.summary}")
        
        if session.decisions:
            lines.append("")
            lines.append("**关键决策**:")
            for d in session.decisions:
                lines.append(f"- {d}")
        
        if session.preferences:
            lines.append("")
            lines.append("**用户偏好**:")
            for p in session.preferences:
                lines.append(f"- {p}")
        
        if session.errors:
            lines.append("")
            lines.append("**错误**:")
            for e in session.errors:
                lines.append(f"- {e}")
        
        content = "\n".join(lines)
        
        # 保存
        entry = await self.memory.append_to_daily(
            content=content,
            tags=["session", "summary"],
        )
        
        return entry

    async def _save_decisions_to_long_term(self) -> None:
        """保存决策到长期记忆"""
        session = self._current_session
        if session is None:
            return
        
        # TODO: 实现追加到 MEMORY.md
        pass

    async def _save_decision_to_long_term(self, decision: str) -> None:
        """保存单个高重要度决策到长期记忆"""
        # TODO: 实现追加到 MEMORY.md
        pass
