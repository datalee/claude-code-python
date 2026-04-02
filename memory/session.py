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

    async def _load_relevant_memories(self, user_id: Optional[str], current_query: str = "") -> List[MemoryEntry]:
        """
        加载相关记忆到会话上下文。
        
        策略：
        1. 提取查询关键词
        2. 计算记忆条目相关性得分
        3. 返回 top-k 相关记忆
        
        Args:
            user_id: 用户 ID
            current_query: 当前查询（用于关键词匹配）
            
        Returns:
            按相关性排序的记忆条目列表
        """
        # 加载所有记忆
        all_entries = []
        
        # 加载每日日记
        today_entries = await self.memory.list_daily()
        all_entries.extend(today_entries)
        
        # 加载用户偏好
        prefs = await self.memory.list_preferences(user_id or "")
        all_entries.extend(prefs)
        
        # 加载决策记忆
        decisions = await self.memory.list_decisions()
        all_entries.extend(decisions)
        
        # 如果没有查询词，返回今天的记忆
        if not current_query:
            return [e for e in all_entries if e.type == MemoryType.DAILY][:10]
        
        # 提取查询关键词
        query_keywords = self._extract_keywords(current_query)
        
        # 计算相关性得分
        scored = []
        for entry in all_entries:
            score = self._calculate_relevance(entry, query_keywords)
            if score > 0:
                scored.append((score, entry))
        
        # 按得分排序，返回 top-10
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:10]]
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        从文本中提取关键词。
        
        使用简单 TF-IDF 启发式：
        - 去除停用词
        - 提取高频词
        - 提取重要实体（项目名、技术栈等）
        
        Args:
            text: 输入文本
            
        Returns:
            关键词列表
        """
        import re
        
        # 停用词列表
        stop_words = {
            '的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
            '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
            '自己', '这', '那', '他', '她', '它', '们', '这个', '那个', '什么', '怎么',
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'may', 'might', 'must', 'can', 'to', 'of', 'in', 'for', 'on', 'with',
            'at', 'by', 'from', 'as', 'into', 'through', 'during', 'before', 'after',
            'and', 'or', 'but', 'if', 'because', 'so', 'that', 'this', 'it', 'i',
        }
        
        # 转为小写，分词
        text_lower = text.lower()
        words = re.findall(r'\b[a-zA-Z\u4e00-\u9fff]{2,}\b', text_lower)
        
        # 过滤停用词和短词
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        # 统计词频
        freq = {}
        for w in keywords:
            freq[w] = freq.get(w, 0) + 1
        
        # 按频率排序，取 top-10
        sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in sorted_words[:10]]
    
    def _calculate_relevance(self, entry: MemoryEntry, keywords: List[str]) -> float:
        """
        计算记忆条目与关键词的相关性得分。
        
        Args:
            entry: 记忆条目
            keywords: 查询关键词列表
            
        Returns:
            相关性得分 (0.0 - 1.0)
        """
        if not keywords:
            return 0.0
        
        # 获取记忆文本
        text = f"{entry.content} {entry.title}".lower()
        
        # 计算命中关键词数
        matches = sum(1 for kw in keywords if kw.lower() in text)
        
        if matches == 0:
            return 0.0
        
        # 得分 = 命中比例 * 权重
        hit_ratio = matches / len(keywords)
        
        # 优先级权重
        priority_weight = {
            MemoryPriority.HIGH: 1.5,
            MemoryPriority.MEDIUM: 1.0,
            MemoryPriority.LOW: 0.5,
        }.get(entry.priority, 1.0)
        
        # 时间衰减（越新的记忆权重越高）
        age_hours = (time.time() - entry.created_at) / 3600
        time_weight = max(0.5, 1.0 - (age_hours / (24 * 30)))  # 最多30天内衰减
        
        return min(1.0, hit_ratio * priority_weight * time_weight)

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
        
        # 保存所有决策
        for decision in session.decisions:
            await self._save_decision_to_long_term(decision)
    
    async def _save_decision_to_long_term(self, decision: str) -> None:
        """
        保存单个高重要度决策到长期记忆。
        
        追加到 memory/long-term.md 文件。
        
        Args:
            decision: 决策内容
        """
        # 长期记忆文件路径
        long_term_file = self.memory.memory_dir / "long-term.md"
        
        # 格式化时间
        dt = datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M")
        
        # 构建要追加的内容
        entry = f"""
## {dt}

**决策**: {decision}

"""
        # 追加到文件
        try:
            long_term_file.parent.mkdir(parents=True, exist_ok=True)
            with open(long_term_file, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception as e:
            self._log(f"Failed to save decision to long-term memory: {e}")
        
        # 同时添加到内存中的记忆列表
        entry_obj = MemoryEntry(
            id=f"decision_{int(time.time() * 1000)}",
            content=decision,
            type=MemoryType.LONG_TERM,
            priority=MemoryPriority.HIGH,
            tags=["decision"],
        )
        self._memory_entries.append(entry_obj)
