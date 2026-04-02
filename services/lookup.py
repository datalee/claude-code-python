"""Lookup Service - Search and Lookup Utilities"""
from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class LookupResult:
    path: str
    line: Optional[int] = None
    match: str = ""
    context: str = ""
    score: float = 0.0


class LookupService:
    def __init__(self) -> None:
        self._indexed_paths: set = set()

    def search_content(self, query: str, root: str = ".", file_pattern: str = "*",
                      case_sensitive: bool = False, regex: bool = False,
                      max_results: int = 50) -> List[LookupResult]:
        results: List[LookupResult] = []
        path = Path(root)
        if not path.exists():
            return results

        try:
            pattern = re.compile(query, re.IGNORECASE if not case_sensitive else 0) if regex else None
            for file_path in path.rglob(file_pattern):
                if not file_path.is_file():
                    continue
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            matched = False
                            if regex and pattern:
                                matched = bool(pattern.search(line))
                            elif case_sensitive:
                                matched = query in line
                            else:
                                matched = query.lower() in line.lower()
                            if matched:
                                results.append(LookupResult(
                                    path=str(file_path), line=line_num,
                                    match=line.strip()[:100], context=line.strip()[:80], score=1.0))
                                if len(results) >= max_results:
                                    return results
                except Exception:
                    continue
        except re.error:
            return results
        return results

    def find_files(self, name: str, root: str = ".", case_sensitive: bool = False) -> List[str]:
        results = []
        path = Path(root)
        if not path.exists():
            return results
        name_lower = name if case_sensitive else name.lower()
        for file_path in path.rglob("*"):
            if file_path.is_file():
                fname = file_path.name if case_sensitive else file_path.name.lower()
                if name_lower == fname or name_lower in fname:
                    results.append(str(file_path))
        return results


_lookup: Optional[LookupService] = None


def get_lookup_service() -> LookupService:
    global _lookup
    if _lookup is None:
        _lookup = LookupService()
    return _lookup


__all__ = ["LookupResult", "LookupService", "get_lookup_service"]
