"""
MemoryCommand - 记忆管理命令

对应 Claude Code 源码: src/commands/memory/

功能：
- 显示记忆状态
- 列出记忆文件
- 搜索记忆
- 添加记忆
- 清理记忆
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from commands.base import Command, CommandContext, CommandResult


class MemoryCommand(Command):
    """记忆管理"""

    name = "memory"
    description = "Manage persistent memory"
    aliases = ["mem"]
    usage = """/memory
    Manage persistent memory.

Commands:
  /memory           - Show memory status
  /memory list      - List memory files
  /memory search <query> - Search memories
  /memory add <text> - Add new memory
  /memory clear     - Clear all memories
  /memory stats     - Show memory statistics"""

    def __init__(self) -> None:
        self._memory_dir = Path.home() / ".claude" / "memory"
        self._index_file = self._memory_dir / ".index.md"
    
    def _get_stats(self) -> Dict[str, Any]:
        """获取记忆统计"""
        stats = {
            "total_files": 0,
            "total_size": 0,
            "by_type": {},
            "oldest": None,
            "newest": None,
        }
        
        if not self._memory_dir.exists():
            return stats
        
        for file_path in self._memory_dir.rglob("*.md"):
            if file_path.name.startswith("."):
                continue
            
            stats["total_files"] += 1
            stats["total_size"] += file_path.stat().st_size
            
            # 按类型统计
            parent = file_path.parent.name
            if parent not in stats["by_type"]:
                stats["by_type"][parent] = 0
            stats["by_type"][parent] += 1
            
            # 时间
            mtime = file_path.stat().st_mtime
            if stats["oldest"] is None or mtime < stats["oldest"]:
                stats["oldest"] = mtime
            if stats["newest"] is None or mtime > stats["newest"]:
                stats["newest"] = mtime
        
        return stats

    def _list_memories(self, limit: int = 20) -> List[Dict[str, Any]]:
        """列出记忆"""
        memories = []
        
        if not self._memory_dir.exists():
            return memories
        
        for file_path in sorted(self._memory_dir.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
            if file_path.name.startswith("."):
                continue
            
            memories.append({
                "name": file_path.stem,
                "path": str(file_path.relative_to(self._memory_dir)),
                "size": file_path.stat().st_size,
                "modified": file_path.stat().st_mtime,
            })
            
            if len(memories) >= limit:
                break
        
        return memories

    def _search_memories(self, query: str) -> List[Dict[str, Any]]:
        """搜索记忆"""
        results = []
        query_lower = query.lower()
        
        if not self._memory_dir.exists():
            return results
        
        for file_path in self._memory_dir.rglob("*.md"):
            if file_path.name.startswith("."):
                continue
            
            try:
                content = file_path.read_text(encoding="utf-8")
                if query_lower in content.lower():
                    # 高亮匹配
                    lines = content.split("\n")
                    matches = [line for line in lines if query_lower in line.lower()]
                    
                    results.append({
                        "name": file_path.stem,
                        "path": str(file_path.relative_to(self._memory_dir)),
                        "matches": matches[:3],  # 最多3个匹配
                    })
            except Exception:
                pass
        
        return results

    async def execute(self, args: List[str], context: CommandContext) -> CommandResult:
        """执行记忆命令"""
        try:
            # 无参数 - 显示状态
            if not args:
                return CommandResult.ok(self._show_status())
            
            subcmd = args[0].lower()
            
            if subcmd == "list":
                return CommandResult.ok(self._list())
            
            elif subcmd == "search":
                if len(args) < 2:
                    return CommandResult.err("Usage: /memory search <query>")
                return CommandResult.ok(self._search(args[1]))
            
            elif subcmd == "add":
                if len(args) < 2:
                    return CommandResult.err("Usage: /memory add <text>")
                return CommandResult.ok(self._add(" ".join(args[1:])))
            
            elif subcmd == "clear":
                return CommandResult.ok(self._clear())
            
            elif subcmd == "stats":
                return CommandResult.ok(self._stats())
            
            else:
                return CommandResult.err(f"Unknown subcommand: {subcmd}")
        
        except Exception as e:
            return CommandResult.err(f"Memory error: {e}")

    def _show_status(self) -> str:
        """显示状态"""
        stats = self._get_stats()
        
        lines = ["\n=== Memory Status ===\n"]
        
        if stats["total_files"] == 0:
            lines.append("No memories stored.")
            lines.append("")
            lines.append("Add memories with: /memory add <text>")
        else:
            lines.append(f"Total files: {stats['total_files']}")
            lines.append(f"Total size: {stats['total_size'] / 1024:.1f} KB")
            
            if stats["by_type"]:
                lines.append("")
                lines.append("By type:")
                for type_name, count in stats["by_type"].items():
                    lines.append(f"  {type_name}: {count}")
        
        lines.append("")
        return "\n".join(lines)

    def _list(self) -> str:
        """列出记忆"""
        memories = self._list_memories()
        
        if not memories:
            return "\nNo memories found.\n"
        
        lines = ["\n=== Memory Files ===\n"]
        for mem in memories:
            modified = time.strftime("%Y-%m-%d %H:%M", time.localtime(mem["modified"]))
            size = mem["size"]
            lines.append(f"  {mem['path']} ({size} bytes, {modified})")
        
        lines.append("")
        return "\n".join(lines)

    def _search(self, query: str) -> str:
        """搜索记忆"""
        results = self._search_memories(query)
        
        if not results:
            return f"\nNo memories found matching: {query}\n"
        
        lines = [f"\n=== Search Results for: {query} ===\n"]
        for result in results:
            lines.append(f"  {result['path']}")
            for match in result["matches"]:
                lines.append(f"    > {match[:100]}")
            lines.append("")
        
        return "\n".join(lines)

    def _add(self, text: str) -> str:
        """添加记忆"""
        # 创建记忆文件
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"memory-{timestamp}.md"
        
        # 确保目录存在
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = self._memory_dir / filename
        content = f"""---
name: Memory {timestamp}
created: {time.strftime("%Y-%m-%d %H:%M:%S")}
type: general
---

{text}
"""
        
        file_path.write_text(content, encoding="utf-8")
        
        return f"\nMemory added: {filename}\n"

    def _clear(self) -> str:
        """清理记忆"""
        count = 0
        for file_path in self._memory_dir.rglob("*.md"):
            if file_path.name.startswith("."):
                continue
            file_path.unlink()
            count += 1
        
        return f"\nCleared {count} memory files.\n"

    def _stats(self) -> str:
        """显示统计"""
        stats = self._get_stats()
        
        lines = ["\n=== Memory Statistics ===\n"]
        lines.append(f"Total files: {stats['total_files']}")
        lines.append(f"Total size: {stats['total_size'] / 1024:.1f} KB")
        
        if stats["oldest"]:
            lines.append(f"Oldest: {time.strftime('%Y-%m-%d %H:%M', time.localtime(stats['oldest']))}")
        if stats["newest"]:
            lines.append(f"Newest: {time.strftime('%Y-%m-%d %H:%M', time.localtime(stats['newest']))}")
        
        if stats["by_type"]:
            lines.append("")
            lines.append("By type:")
            for type_name, count in stats["by_type"].items():
                lines.append(f"  {type_name}: {count}")
        
        lines.append("")
        return "\n".join(lines)
