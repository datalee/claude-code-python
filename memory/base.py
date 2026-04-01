"""
Memory Base - 记忆抽象基类

定义记忆系统的核心接口和数据结构。
对应 Claude Code 源码: src/memory/Memory.ts
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class MemoryType(Enum):
    """
    记忆类型枚举。
    对应 Claude Code 源码: src/memory/MemoryType
    """
    DAILY = "daily"           # 每日日记（自动追加）
    LONG_TERM = "long_term"   # 长期记忆（手动整理）
    SESSION = "session"       # 会话记忆（单次对话）
    COMPACTED = "compacted"   # 压缩后的记忆


class MemoryPriority(Enum):
    """
    记忆优先级。
    用于决定压缩时保留哪些记忆。
    """
    HIGH = "high"     # 高优先级，永不删除
    MEDIUM = "medium" # 中优先级，可压缩
    LOW = "low"      # 低优先级，优先删除


@dataclass
class MemoryEntry:
    """
    单条记忆条目。
    对应 Claude Code 源码: src/memory/MemoryEntry
    
    Attributes:
        id: 记忆唯一标识符
        content: 记忆内容（Markdown 格式）
        type: 记忆类型（daily/long_term/session）
        priority: 记忆优先级
        tags: 标签列表，用于分类和检索
        created_at: 创建时间戳
        updated_at: 更新时间戳
        metadata: 额外元数据
    """
    id: str
    content: str
    type: MemoryType = MemoryType.SESSION
    priority: MemoryPriority = MemoryPriority.MEDIUM
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def created_time(self) -> datetime:
        """返回可读的创建时间"""
        return datetime.fromtimestamp(self.created_at)

    @property
    def updated_time(self) -> datetime:
        """返回可读的更新时间"""
        return datetime.fromtimestamp(self.updated_at)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "id": self.id,
            "content": self.content,
            "type": self.type.value,
            "priority": self.priority.value,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    def to_markdown(self) -> str:
        """
        转换为 Markdown 格式。
        用于写入记忆文件。
        """
        lines = [
            f"## {self.created_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**类型**: {self.type.value} | **优先级**: {self.priority.value}",
        ]
        if self.tags:
            lines.append(f"**标签**: {', '.join(self.tags)}")
        lines.append("")
        lines.append(self.content)
        return "\n".join(lines)


class MemoryBase(ABC):
    """
    记忆抽象基类。
    对应 Claude Code 源码: src/memory/Memory (基类)
    
    所有记忆实现必须继承此类并实现核心方法。
    
    设计原则：
    1. 记忆以 Markdown 文件形式存储（人类可读）
    2. 支持分层记忆（daily/long_term/session）
    3. 自动追踪访问模式和重要性
    4. 支持向量搜索（可选）
    
    示例：
        class FileMemory(MemoryBase):
            async def save(self, entry: MemoryEntry) -> None:
                ...
            
            async def search(self, query: str) -> List[MemoryEntry]:
                ...
    """

    def __init__(
        self,
        workspace_path: str | Path,
        daily记忆_dir: str = "memory",
        long_term_file: str = "MEMORY.md",
    ) -> None:
        """
        初始化记忆基类。
        
        Args:
            workspace_path: 工作空间根路径
            daily记忆_dir: 每日记忆目录名
            long_term_file: 长期记忆文件名
        """
        self.workspace_path = Path(workspace_path)
        self.daily记忆_dir = self.workspace_path / daily记忆_dir
        self.long_term_file = self.workspace_path / long_term_file
        
        # 确保目录存在
        self.daily记忆_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    async def save(self, entry: MemoryEntry) -> None:
        """
        保存一条记忆。
        
        Args:
            entry: 记忆条目
        """
        raise NotImplementedError

    @abstractmethod
    async def load(self, memory_id: str) -> Optional[MemoryEntry]:
        """
        加载指定记忆。
        
        Args:
            memory_id: 记忆 ID
            
        Returns:
            记忆条目，不存在返回 None
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """
        删除指定记忆。
        
        Args:
            memory_id: 记忆 ID
            
        Returns:
            是否删除成功
        """
        raise NotImplementedError

    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int = 10,
        memory_type: Optional[MemoryType] = None,
    ) -> List[MemoryEntry]:
        """
        搜索记忆。
        
        Args:
            query: 搜索关键词
            limit: 返回数量限制
            memory_type: 限定记忆类型
            
        Returns:
            匹配的记忆条目列表
        """
        raise NotImplementedError

    @abstractmethod
    async def list_daily(self, date: Optional[datetime] = None) -> List[MemoryEntry]:
        """
        列出指定日期的日记。
        
        Args:
            date: 日期（None 表示今天）
            
        Returns:
            该日期的记忆条目列表
        """
        raise NotImplementedError

    @abstractmethod
    async def get_long_term(self) -> List[MemoryEntry]:
        """
        获取长期记忆。
        
        Returns:
            长期记忆条目列表
        """
        raise NotImplementedError

    # -------------------------------------------------------------------------
    # 工具方法（提供默认实现，可被子类覆盖）
    # -------------------------------------------------------------------------

    def get_daily_file_path(self, date: Optional[datetime] = None) -> Path:
        """
        获取指定日期的日记文件路径。
        
        Args:
            date: 日期（None 表示今天）
            
        Returns:
            文件路径
        """
        if date is None:
            date = datetime.now()
        return self.daily记忆_dir / f"{date.strftime('%Y-%m-%d')}.md"

    def generate_id(self) -> str:
        """
        生成唯一的记忆 ID。
        
        Returns:
            记忆 ID 格式: mem_{timestamp}_{random}
        """
        import uuid
        return f"mem_{int(time.time())}_{uuid.uuid4().hex[:8]}"

    async def append_to_daily(
        self,
        content: str,
        tags: Optional[List[str]] = None,
        date: Optional[datetime] = None,
    ) -> MemoryEntry:
        """
        追加内容到每日日记。
        
        这是最高效的写入方式，只追加不修改。
        
        Args:
            content: 要追加的内容（Markdown 格式）
            tags: 可选标签
            date: 日期（None 表示今天）
            
        Returns:
            创建的记忆条目
        """
        entry = MemoryEntry(
            id=self.generate_id(),
            content=content,
            type=MemoryType.DAILY,
            tags=tags or [],
        )
        
        file_path = self.get_daily_file_path(date)
        
        # 追加到文件
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"\n{entry.to_markdown()}\n")
        
        return entry

    async def update_long_term(self, content: str) -> MemoryEntry:
        """
        更新长期记忆文件。
        
        长期记忆文件由用户手动整理，框架只负责读取。
        此方法用于初始化或完全覆盖。
        
        Args:
            content: Markdown 内容
            
        Returns:
            创建的记忆条目
        """
        entry = MemoryEntry(
            id=self.generate_id(),
            content=content,
            type=MemoryType.LONG_TERM,
            priority=MemoryPriority.HIGH,
        )
        
        with open(self.long_term_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        return entry

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} workspace={self.workspace_path}>"
