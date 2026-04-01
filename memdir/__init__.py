"""
Memory Directory - 记忆目录管理

管理持久化记忆的目录结构和检索。
对应 Claude Code 源码: src/memdir/memdir.ts

核心设计：
1. 记忆以 .md 文件存储，每个文件一个记忆
2. MEMORY.md 是索引文件，列出所有记忆的入口
3. findRelevantMemories() 用 LLM 选择相关记忆

记忆类型：
- user: 用户信息、偏好、习惯
- feedback: 反馈、改进建议
- project: 项目相关上下文
- reference: 参考资料、文档链接
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, List, Optional

from agent.query_engine import QueryEngine, AgentConfig


# =============================================================================
# 常量
# =============================================================================

MEMORY_DIR_NAME = "memory"
ENTRYPOINT_NAME = "MEMORY.md"
MAX_ENTRYPOINT_LINES = 200
MAX_ENTRYPOINT_BYTES = 25_000
MAX_MEMORY_FILES = 200
FRONTMATTER_MAX_LINES = 30


class MemoryType(Enum):
    """记忆类型枚举"""
    USER = "user"           # 用户信息、偏好
    FEEDBACK = "feedback"   # 反馈、改进建议
    PROJECT = "project"      # 项目上下文
    REFERENCE = "reference"   # 参考资料
    TEAM = "team"          # 团队记忆（多 Agent）
    PRIVATE = "private"     # 私有记忆


# =============================================================================
# Frontmatter 解析
# =============================================================================

FRONTMATTER_REGEX = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(content: str) -> dict[str, Any]:
    """
    解析 Markdown frontmatter。

    格式：
    ---
    name: Memory Name
    description: 简短的描述
    type: user
    tags: [tag1, tag2]
    ---
    # 实际内容
    """
    match = FRONTMATTER_REGEX.match(content)
    if not match:
        return {}

    fm = {}
    for line in match.group(1).split("\n"):
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
            
            fm[key] = value

    return fm


def format_frontmatter(
    name: str,
    description: str,
    memory_type: MemoryType,
    tags: Optional[List[str]] = None,
) -> str:
    """生成 frontmatter 头"""
    lines = [
        "---",
        f"name: {name}",
        f"description: {description}",
        f"type: {memory_type.value}",
    ]
    if tags:
        lines.append(f"tags: [{', '.join(tags)}]")
    lines.append("---")
    return "\n".join(lines)


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class MemoryHeader:
    """
    记忆文件头信息。
    
    从 frontmatter 解析得到，不包含正文内容。
    """
    filename: str           # 文件名
    file_path: str          # 完整路径
    mtime_ms: float         # 修改时间（毫秒时间戳）
    description: Optional[str] = None  # 描述
    memory_type: Optional[MemoryType] = None  # 类型
    name: Optional[str] = None  # 记忆名称
    tags: List[str] = field(default_factory=list)  # 标签


@dataclass
class MemoryContent:
    """记忆完整内容"""
    header: MemoryHeader
    content: str  # 除去 frontmatter 的正文


@dataclass
class EntrypointTruncation:
    """截断结果"""
    content: str
    line_count: int
    byte_count: int
    was_line_truncated: bool
    was_byte_truncated: bool


# =============================================================================
# 核心函数
# =============================================================================

def truncate_entrypoint_content(raw: str) -> EntrypointTruncation:
    """
    截断 MEMORY.md 内容到行数和字节数上限。

    优先按行截断，再按字节截断。
    如果触发了截断，会在末尾添加警告。

    Args:
        raw: 原始内容

    Returns:
        截断结果
    """
    trimmed = raw.strip()
    content_lines = trimmed.split("\n")
    line_count = len(content_lines)
    byte_count = len(trimmed.encode("utf-8"))

    was_line_truncated = line_count > MAX_ENTRYPOINT_LINES
    was_byte_truncated = byte_count > MAX_ENTRYPOINT_BYTES

    if not was_line_truncated and not was_byte_truncated:
        return EntrypointTruncation(
            content=trimmed,
            line_count=line_count,
            byte_count=byte_count,
            was_line_truncated=False,
            was_byte_truncated=False,
        )

    # 先按行截断
    truncated = (
        content_lines[:MAX_ENTRYPOINT_LINES]
        if was_line_truncated
        else trimmed
    )

    # 再按字节截断
    truncated_bytes = truncated.encode("utf-8")
    if len(truncated_bytes) > MAX_ENTRYPOINT_BYTES:
        cut_at = truncated.rfind("\n", 0, MAX_ENTRYPOINT_BYTES)
        if cut_at > 0:
            truncated = truncated[:cut_at]
        else:
            truncated = truncated[:MAX_ENTRYPOINT_BYTES]

    # 生成警告信息
    if was_byte_truncated and not was_line_truncated:
        reason = f"{byte_count} bytes (limit: {MAX_ENTRYPOINT_BYTES})"
    elif was_line_truncated and not was_byte_truncated:
        reason = f"{line_count} lines (limit: {MAX_ENTRYPOINT_LINES})"
    else:
        reason = f"{line_count} lines and {byte_count} bytes"

    warning = (
        f"\n\n> WARNING: {ENTRYPOINT_NAME} is {reason}. "
        "Only part of it was loaded. "
        "Keep index entries to one line under ~200 chars."
    )

    return EntrypointTruncation(
        content=truncated + warning,
        line_count=line_count,
        byte_count=byte_count,
        was_line_truncated=was_line_truncated,
        was_byte_truncated=was_byte_truncated,
    )


async def ensure_memory_dir_exists(memory_dir: str) -> None:
    """
    确保记忆目录存在。

    幂等操作，多次调用无副作用。
    """
    Path(memory_dir).mkdir(parents=True, exist_ok=True)


def build_memory_prompt_lines(
    display_name: str,
    memory_dir: str,
    skip_index: bool = False,
) -> List[str]:
    """
    构建记忆系统的行为指导文本。

    这段文本会被插入到系统提示中，告诉 Agent 如何使用记忆系统。

    Args:
        display_name: 显示名称
        memory_dir: 记忆目录路径
        skip_index: 是否跳过索引步骤（某些场景下不需要写索引）

    Returns:
        指导文本的行列表
    """
    how_to_save = (
        [
            "## How to save memories",
            "",
            "Write each memory to its own file (e.g., `user_role.md`, `feedback_testing.md`) using this frontmatter format:",
            "",
            '```yaml',
            "name: Memory Name",
            "description: Brief description of what this memory contains",
            "type: user  # options: user | feedback | project | reference",
            "tags: [optional, tags]",
            "---",
            "# Memory content here...",
            '```',
            "",
            "- Keep the name, description, and type fields in memory files up-to-date",
            "- Organize memory semantically by topic, not chronologically",
            "- Update or remove memories that turn out to be wrong or outdated",
            "- Do not write duplicate memories. Check for existing memory before writing a new one.",
        ]
        if skip_index
        else [
            "## How to save memories",
            "",
            "Saving a memory is a two-step process:",
            "",
            "**Step 1** — write the memory to its own file (e.g., `user_role.md`) using this frontmatter format:",
            "",
            '```yaml',
            "name: Memory Name",
            "description: Brief description",
            "type: user",
            "---",
            "# Memory content here...",
            '```',
            "",
            f"**Step 2** — add a pointer to `{ENTRYPOINT_NAME}`. "
            f"`{ENTRYPOINT_NAME}` is an index, not a memory — each entry should be one line:",
            "",
            f"`- [Title](file.md) — one-line hook`",
            "",
            f"- `{ENTRYPOINT_NAME}` has a {MAX_ENTRYPOINT_LINES}-line limit — keep the index concise",
            "- Keep the name, description, and type fields in memory files up-to-date",
            "- Organize memory semantically by topic, not chronologically",
            "- Update or remove memories that turn out to be wrong or outdated",
            "- Do not write duplicate memories. Check for existing memory before writing a new one.",
        ]
    )

    types_section = [
        "## Memory types",
        "",
        "Use one of these four types for every memory:",
        "",
        "- **user** — user preferences, habits, communication style",
        "- **feedback** — what the user likes, dislikes, or wants you to improve",
        "- **project** — project-specific context, architecture, conventions",
        "- **reference** — external documentation, links, resources",
        "",
    ]

    when_not_to_save = [
        "## What NOT to save",
        "",
        "- Information derivable from current project state (code patterns, git history)",
        "- Routine outputs (lint results, test runs, build output)",
        "- Content better kept in a Plan or file within the project",
        "- Information only useful in the current conversation",
        "",
    ]

    when_to_access = [
        "## When to access memory",
        "",
        "- At the start of each conversation",
        "- When the user introduces themselves or mentions preferences",
        "- When working on a project you've seen before",
        "- When the user asks you to 'remember' something",
        "",
    ]

    trusting_recall = [
        "## Trusting memory recall",
        "",
        "The memory system has semantic search — you can trust it to find relevant",
        "memories even if you don't recall them exactly. Don't second-guess it.",
        "",
    ]

    memory_and_persistence = [
        "## Memory and other forms of persistence",
        "",
        "Memory is one of several persistence mechanisms. Use a Plan rather than memory",
        "when you want to align on an approach before starting implementation.",
        "",
    ]

    lines = (
        [f"# {display_name}", ""]
        + [f"Memory is stored at `{memory_dir}`. Write to it directly with the Write tool.", ""]
        + [
            "Build up memory over time so future conversations can have a",
            "complete picture of the user, their preferences, and project context.",
            "",
        ]
        + when_not_to_save
        + types_section
        + how_to_save
        + when_to_access
        + trusting_recall
        + memory_and_persistence
    )

    return lines
