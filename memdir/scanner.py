"""
Memory Scanner - 记忆文件扫描

扫描记忆目录，读取 frontmatter 提取元数据。
对应 Claude Code 源码: src/memdir/memoryScan.ts
"""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import List, Optional

from memdir import (
    FRONTMATTER_MAX_LINES,
    MAX_MEMORY_FILES,
    MemoryHeader,
    MemoryType,
    parse_frontmatter,
)


async def scan_memory_files(
    memory_dir: str,
    signal: Optional[asyncio.Event] = None,
) -> List[MemoryHeader]:
    """
    扫描记忆目录，返回所有 .md 文件的头信息。

    流程：
    1. 递归扫描目录，找到所有 .md 文件
    2. 并行读取每个文件的前 N 行，解析 frontmatter
    3. 按修改时间倒序排序
    4. 限制返回数量（最多 MAX_MEMORY_FILES）

    Args:
        memory_dir: 记忆目录路径
        signal: 中断信号

    Returns:
        MemoryHeader 列表，按 mtime 倒序
    """
    try:
        entries = []
        for root, dirs, files in os.walk(memory_dir):
            for filename in files:
                if filename.endswith(".md") and filename != "MEMORY.md":
                    entries.append(os.path.join(root, filename))
    except OSError:
        return []

    # 并行读取所有文件
    async def read_one(file_path: str) -> Optional[MemoryHeader]:
        if signal and signal.is_set():
            return None

        try:
            return await _read_memory_header(file_path)
        except Exception:
            return None

    results = await asyncio.gather(*[read_one(f) for f in entries])

    # 过滤成功的结果
    headers = [r for r in results if r is not None]

    # 按 mtime 倒序排序
    headers.sort(key=lambda h: h.mtime_ms, reverse=True)

    # 限制数量
    return headers[:MAX_MEMORY_FILES]


async def _read_memory_header(file_path: str) -> Optional[MemoryHeader]:
    """
    读取单个记忆文件的头部信息。

    Args:
        file_path: 文件路径

    Returns:
        MemoryHeader 或 None
    """
    stat = os.stat(file_path)
    mtime_ms = stat.st_mtime * 1000  # 转为毫秒

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = []
            blank_count = 0
            in_frontmatter = False
            frontmatter_lines = 0

            for i, line in enumerate(f):
                if i >= FRONTMATTER_MAX_LINES:
                    break

                # 检测 frontmatter 边界
                if line.strip() == "---":
                    if not in_frontmatter:
                        in_frontmatter = True
                        continue
                    else:
                        # frontmatter 结束
                        break

                if in_frontmatter:
                    frontmatter_lines += 1
                    lines.append(line)

                # 检测意外的主内容开始
                if not in_frontmatter and line.startswith("# "):
                    break

        # 解析 frontmatter
        frontmatter_text = "".join(lines)
        fm = _parse_frontmatter_text(frontmatter_text)

        # 计算相对路径（相对于 memory_dir）
        rel_path = os.path.relpath(file_path, os.path.dirname(os.path.dirname(file_path)))

        return MemoryHeader(
            filename=os.path.basename(file_path),
            file_path=file_path,
            mtime_ms=mtime_ms,
            name=fm.get("name"),
            description=fm.get("description"),
            memory_type=_parse_memory_type(fm.get("type")),
            tags=fm.get("tags", []),
        )

    except Exception:
        return None


def _parse_frontmatter_text(text: str) -> dict:
    """解析 frontmatter 文本"""
    fm = {}
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if ": " in line:
            key, value = line.split(": ", 1)
            key = key.strip()
            value = value.strip().strip('"\'')

            # 解析数组
            if value.startswith("[") and value.endswith("]"):
                value = [v.strip().strip('"\'') for v in value[1:-1].split(",")]
            elif value.lower() in ("true", "false"):
                value = value.lower() == "true"

            fm[key] = value

    return fm


def _parse_memory_type(type_str: Optional[str]) -> Optional[MemoryType]:
    """解析记忆类型字符串"""
    if not type_str:
        return None

    type_map = {
        "user": MemoryType.USER,
        "feedback": MemoryType.FEEDBACK,
        "project": MemoryType.PROJECT,
        "reference": MemoryType.REFERENCE,
        "team": MemoryType.TEAM,
        "private": MemoryType.PRIVATE,
    }

    return type_map.get(type_str.lower())


def format_memory_manifest(headers: List[MemoryHeader]) -> str:
    """
    将记忆头列表格式化为文本清单。

    用于：
    1. 展示给 LLM 选择相关记忆
    2. 提取 Agent 的 prompt

    格式：
    - [type] filename (timestamp): description
    - [type] filename (timestamp)

    Args:
        headers: 记忆头列表

    Returns:
        格式化的清单文本
    """
    lines = []

    for h in headers:
        # 类型标签
        type_tag = f"[{h.memory_type.value}] " if h.memory_type else ""

        # 时间戳
        ts = datetime.fromtimestamp(h.mtime_ms / 1000).isoformat()

        # 描述
        if h.description:
            lines.append(f"- {type_tag}{h.filename} ({ts}): {h.description}")
        else:
            lines.append(f"- {type_tag}{h.filename} ({ts})")

    return "\n".join(lines)


def read_memory_content(file_path: str, max_chars: Optional[int] = None) -> str:
    """
    读取记忆文件的正文内容。

    Args:
        file_path: 文件路径
        max_chars: 最大字符数（截断用）

    Returns:
        文件正文
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 移除 frontmatter
        content = FRONTMATTER_REGEX.sub("", content, count=1).strip()

        if max_chars and len(content) > max_chars:
            content = content[:max_chars] + "\n\n... [truncated]"

        return content

    except Exception:
        return ""


# 编译 frontmatter 正则
FRONTMATTER_REGEX = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
