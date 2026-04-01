"""
History Module - 命令历史管理

持久化存储和搜索命令历史。
对应 Claude Code 源码: src/history/*.ts
"""

from __future__ import annotations

import codecs
import json
import os
import readline
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class HistoryEntry:
    """历史条目"""
    id: str           # 唯一 ID
    command: str      # 命令内容
    timestamp: float   # Unix 时间戳
    session_id: str   # 所属会话 ID
    exit_code: Optional[int] = None  # 退出码
    duration_ms: Optional[int] = None  # 执行耗时
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistoryEntry":
        return cls(**data)


# ============================================================================
# HistoryStore
# ============================================================================

class HistoryStore:
    """
    命令历史持久化存储。
    
    将命令历史存储在 JSONL 文件中，支持：
    - 按会话分组
    - 全文搜索
    - 时间范围过滤
    - 统计信息
    
    文件格式：JSONL（每行一个 JSON）
    """
    
    DEFAULT_HISTORY_FILE = Path.home() / ".claude" / "history.jsonl"
    
    def __init__(
        self,
        history_file: Optional[Path] = None,
        max_entries: int = 10000,
    ) -> None:
        """
        初始化历史存储。
        
        Args:
            history_file: 历史文件路径
            max_entries: 最大保留条目数（超过时删除旧条目）
        """
        self.history_file = history_file or self.DEFAULT_HISTORY_FILE
        self.max_entries = max_entries
        
        # 确保目录存在
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
    
    # =========================================================================
    # 读写操作
    # =========================================================================
    
    def add(
        self,
        command: str,
        session_id: str,
        exit_code: Optional[int] = None,
        duration_ms: Optional[int] = None,
    ) -> HistoryEntry:
        """
        添加一条历史记录。
        
        Args:
            command: 命令内容
            session_id: 会话 ID
            exit_code: 退出码
            duration_ms: 执行耗时（毫秒）
            
        Returns:
            创建的历史条目
        """
        import uuid
        
        entry = HistoryEntry(
            id=f"hist_{uuid.uuid4().hex[:12]}",
            command=command,
            timestamp=time.time(),
            session_id=session_id,
            exit_code=exit_code,
            duration_ms=duration_ms,
        )
        
        # 追加到文件
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        
        # 清理旧条目
        self._cleanup()
        
        return entry
    
    def _cleanup(self) -> None:
        """清理超出限制的旧条目"""
        if not self.history_file.exists():
            return
        
        # 读取所有条目
        entries = self._read_all()
        
        if len(entries) <= self.max_entries:
            return
        
        # 保留最新的 N 条
        entries = entries[-self.max_entries:]
        
        # 重写文件
        with open(self.history_file, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
    
    def _read_all(self) -> List[HistoryEntry]:
        """读取所有历史条目"""
        if not self.history_file.exists():
            return []
        
        entries = []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(HistoryEntry.from_dict(json.loads(line)))
                        except (json.JSONDecodeError, TypeError):
                            continue
        except FileNotFoundError:
            pass
        
        return entries
    
    # =========================================================================
    # 查询操作
    # =========================================================================
    
    def get_recent(self, limit: int = 20, session_id: Optional[str] = None) -> List[HistoryEntry]:
        """
        获取最近的历史条目。
        
        Args:
            limit: 返回数量
            session_id: 可选，限定会话
            
        Returns:
            历史条目列表（按时间逆序）
        """
        entries = self._read_all()
        
        if session_id:
            entries = [e for e in entries if e.session_id == session_id]
        
        # 逆序，返回最新的
        return list(reversed(entries[-limit:]))
    
    def search(
        self,
        query: str,
        limit: int = 20,
        session_id: Optional[str] = None,
    ) -> List[HistoryEntry]:
        """
        搜索历史条目。
        
        Args:
            query: 搜索关键词
            limit: 返回数量
            session_id: 可选，限定会话
            
        Returns:
            匹配的历史条目列表
        """
        entries = self._read_all()
        
        if session_id:
            entries = [e for e in entries if e.session_id == session_id]
        
        # 模糊匹配
        query_lower = query.lower()
        matched = [e for e in entries if query_lower in e.command.lower()]
        
        # 逆序，返回最新的
        return list(reversed(matched[-limit:]))
    
    def get_by_session(self, session_id: str) -> List[HistoryEntry]:
        """
        获取指定会话的所有历史。
        
        Args:
            session_id: 会话 ID
            
        Returns:
            该会话的历史条目列表（按时间顺序）
        """
        entries = self._read_all()
        return [e for e in entries if e.session_id == session_id]
    
    def get_sessions(self) -> List[str]:
        """
        获取所有会话 ID。
        
        Returns:
            会话 ID 列表（去重）
        """
        entries = self._read_all()
        seen = set()
        sessions = []
        for e in entries:
            if e.session_id not in seen:
                seen.add(e.session_id)
                sessions.append(e.session_id)
        return sessions
    
    # =========================================================================
    # 统计信息
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取历史统计信息。
        
        Returns:
            统计字典
        """
        entries = self._read_all()
        
        if not entries:
            return {
                "total": 0,
                "sessions": 0,
                "oldest": None,
                "newest": None,
            }
        
        # 按会话分组
        sessions: Dict[str, List[HistoryEntry]] = {}
        for e in entries:
            if e.session_id not in sessions:
                sessions[e.session_id] = []
            sessions[e.session_id].append(e)
        
        return {
            "total": len(entries),
            "sessions": len(sessions),
            "oldest": datetime.fromtimestamp(entries[0].timestamp).isoformat() if entries else None,
            "newest": datetime.fromtimestamp(entries[-1].timestamp).isoformat() if entries else None,
            "per_session": {sid: len(ents) for sid, ents in sessions.items()},
        }
    
    # =========================================================================
    # 管理操作
    # =========================================================================
    
    def clear_session(self, session_id: str) -> int:
        """
        清除指定会话的历史。
        
        Args:
            session_id: 会话 ID
            
        Returns:
            删除的条目数
        """
        entries = self._read_all()
        remaining = [e for e in entries if e.session_id != session_id]
        removed = len(entries) - len(remaining)
        
        if removed > 0:
            with open(self.history_file, "w", encoding="utf-8") as f:
                for entry in remaining:
                    f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        
        return removed
    
    def clear_all(self) -> None:
        """清除所有历史"""
        if self.history_file.exists():
            self.history_file.unlink()


# ============================================================================
# readline 集成
# ============================================================================

class ReadlineHistory:
    """
    readline 历史管理器。
    
    提供与 Python readline 模块的集成，
    支持持久化历史存储。
    """
    
    def __init__(
        self,
        history_file: Optional[Path] = None,
        history_length: int = 1000,
    ) -> None:
        """
        初始化 readline 历史管理。
        
        Args:
            history_file: 历史文件路径
            history_length: readline 保留历史数
        """
        if history_file is None:
            history_file = Path.home() / ".claude" / "readline_history"
        
        self.history_file = history_file
        self.history_length = history_length
        
        # 确保目录存在
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
    
    def load(self) -> None:
        """加载历史到 readline"""
        if not self.history_file.exists():
            return
        
        try:
            readline.read_history_file(str(self.history_file))
            readline.set_history_length(self.history_length)
        except Exception:
            pass
    
    def save(self) -> None:
        """保存 readline 历史到文件"""
        try:
            readline.write_history_file(str(self.history_file))
        except Exception:
            pass
    
    def add(self, line: str) -> None:
        """
        添加一行到历史。
        
        Args:
            line: 命令行
        """
        if line and line.strip():
            readline.add_history(line)


# ============================================================================
# 全局实例
# ============================================================================

_store: Optional[HistoryStore] = None
_readline_history: Optional[ReadlineHistory] = None


def get_history_store() -> HistoryStore:
    """获取全局历史存储实例"""
    global _store
    if _store is None:
        _store = HistoryStore()
    return _store


def get_readline_history() -> ReadlineHistory:
    """获取全局 readline 历史实例"""
    global _readline_history
    if _readline_history is None:
        _readline_history = ReadlineHistory()
    return _readline_history


__all__ = [
    "HistoryEntry",
    "HistoryStore",
    "ReadlineHistory",
    "get_history_store",
    "get_readline_history",
]
