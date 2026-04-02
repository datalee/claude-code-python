"""Mind Service - Memory and Knowledge Management"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class MemoryEntry:
    id: str
    content: str
    type: str
    tags: Set[str] = field(default_factory=set)
    importance: float = 0.5
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class Mind:
    def __init__(self) -> None:
        self._memories: Dict[str, MemoryEntry] = {}
        self._next_id = 1

    def add_memory(self, content: str, memory_type: str = "fact",
                   tags: Optional[Set[str]] = None, importance: float = 0.5) -> str:
        entry_id = f"mem_{self._next_id}"
        self._next_id += 1
        entry = MemoryEntry(id=entry_id, content=content, type=memory_type,
                            tags=tags or set(), importance=importance)
        self._memories[entry_id] = entry
        return entry_id

    def get_memory(self, entry_id: str) -> Optional[MemoryEntry]:
        entry = self._memories.get(entry_id)
        if entry:
            entry.access_count += 1
            entry.accessed_at = time.time()
        return entry

    def search_memories(self, query: str, memory_type: Optional[str] = None,
                       tags: Optional[Set[str]] = None, limit: int = 10) -> List[MemoryEntry]:
        results = []
        for entry in self._memories.values():
            if memory_type and entry.type != memory_type:
                continue
            if tags and not tags.intersection(entry.tags):
                continue
            if query.lower() in entry.content.lower() or any(query.lower() in t.lower() for t in entry.tags):
                results.append(entry)
        results.sort(key=lambda e: e.importance, reverse=True)
        return results[:limit]

    def forget_memory(self, entry_id: str) -> bool:
        if entry_id in self._memories:
            del self._memories[entry_id]
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        by_type: Dict[str, int] = {}
        for entry in self._memories.values():
            by_type[entry.type] = by_type.get(entry.type, 0) + 1
        return {"total": len(self._memories), "by_type": by_type}


_mind: Optional[Mind] = None


def get_mind() -> Mind:
    global _mind
    if _mind is None:
        _mind = Mind()
    return _mind


__all__ = ["MemoryEntry", "Mind", "get_mind"]
