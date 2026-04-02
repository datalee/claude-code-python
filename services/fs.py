"""FS Service - File System Operations"""
from __future__ import annotations
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class FileInfo:
    path: str
    name: str
    is_file: bool
    is_dir: bool
    size: int
    modified: float


class FSService:
    def read_file(self, path: str) -> str:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def write_file(self, path: str, content: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def delete_file(self, path: str) -> None:
        p = Path(path)
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            shutil.rmtree(p)

    def list_dir(self, path: str, include_hidden: bool = False) -> List[str]:
        p = Path(path)
        if not p.is_dir():
            return []
        entries = [e.name for e in p.iterdir() if include_hidden or not e.name.startswith(".")]
        return sorted(entries)

    def exists(self, path: str) -> bool:
        return Path(path).exists()

    def get_file_info(self, path: str) -> Optional[FileInfo]:
        p = Path(path)
        if not p.exists():
            return None
        stat = p.stat()
        return FileInfo(path=str(p), name=p.name, is_file=p.is_file(), is_dir=p.is_dir(),
                       size=stat.st_size, modified=stat.st_mtime)


_fs: Optional[FSService] = None


def get_fs_service() -> FSService:
    global _fs
    if _fs is None:
        _fs = FSService()
    return _fs


__all__ = ["FileInfo", "FSService", "get_fs_service"]
