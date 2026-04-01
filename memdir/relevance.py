"""
findRelevantMemories - 语义检索相关记忆

使用 LLM 从记忆清单中选择相关的记忆。
对应 Claude Code 源码: src/memdir/findRelevantMemories.ts

核心设计：
1. scanMemoryFiles() 扫描所有记忆文件，提取 header
2. formatMemoryManifest() 将 header 格式化为清单
3. 调用 LLM（Sonnet）选择最相关的记忆
4. 返回命中的记忆文件路径
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from agent.query_engine import QueryEngine, AgentConfig


# =============================================================================
# Prompt 模板
# =============================================================================

SELECT_MEMORIES_SYSTEM_PROMPT = """You are selecting memories that will be useful
to Claude Code as it processes a user's query. You will be given the user's query
and a list of available memory files with their filenames and descriptions.

Return a JSON object with a 'selected_memories' array containing filenames
for the memories that will clearly be useful (up to 5).

Rules:
- Only include memories that you are certain will be helpful
- If there are recently-used tools, do not select API documentation for those tools
- DO select memories containing warnings, gotchas, or known issues
- Prefer specific memories over general ones
- If no memories are relevant, return an empty array
"""

SELECT_MEMORIES_USER_PROMPT = """Query: {query}

Available memories:
{memories_manifest}

Return JSON: {{"selected_memories": ["file1.md", "file2.md"]}}"""


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class RelevanceResult:
    """语义检索结果"""
    selected_memories: List[str]  # 选中的记忆文件名
    scores: Dict[str, float]  # 每个记忆的得分（可选）


# =============================================================================
# findRelevantMemories
# =============================================================================

async def find_relevant_memories(
    query: str,
    memory_manifest: str,
    llm_client: Any = None,
    model: str = "claude-sonnet-4-20250514",
) -> RelevanceResult:
    """
    从记忆清单中选择与查询相关的记忆。

    核心流程：
    1. 构建 prompt（包含 query 和记忆清单）
    2. 调用 LLM（Sonnet）让模型选择
    3. 解析 JSON 响应
    4. 返回选中的记忆文件名列表

    Args:
        query: 用户查询
        memory_manifest: 格式化的记忆清单（来自 scanner.format_memory_manifest）
        llm_client: LLM 客户端（AsyncAnthropic）
        model: 使用的模型

    Returns:
        RelevanceResult，包含选中的记忆文件名列表

    示例：
        headers = await scan_memory_files("./memory")
        manifest = format_memory_manifest(headers)
        result = await find_relevant_memories(
            query="How does the user like to collaborate?",
            memory_manifest=manifest,
            llm_client=client,
        )
        for filename in result.selected_memories:
            print(f"Selected: {filename}")
    """
    # 构建 prompt
    user_prompt = SELECT_MEMORIES_USER_PROMPT.format(
        query=query,
        memories_manifest=memory_manifest or "(no memories available)",
    )

    # 调用 LLM
    try:
        if llm_client:
            # 使用提供的 LLM 客户端
            response = await _call_llm(llm_client, model, user_prompt)
        else:
            # 使用默认方式（如果有配置）
            response = await _call_default_llm(model, user_prompt)

        # 解析响应
        result = _parse_llm_response(response)
        return result

    except Exception as e:
        # 如果 LLM 调用失败，返回空结果
        return RelevanceResult(selected_memories=[], scores={})


async def _call_llm(client: Any, model: str, user_prompt: str) -> str:
    """调用 LLM"""
    try:
        # 尝试新版 API
        if hasattr(client, 'messages'):
            response = await client.messages.create(
                model=model,
                max_tokens=512,
                system=SELECT_MEMORIES_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text
    except Exception:
        pass

    # 降级到简单实现
    raise RuntimeError("LLM call failed")


async def _call_default_llm(model: str, user_prompt: str) -> str:
    """
    调用默认 LLM（需要环境变量 ANTHROPIC_API_KEY）。

    如果没有配置 LLM 客户端，可以调用这个函数。
    """
    import os
    from anthropic import AsyncAnthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    client = AsyncAnthropic(api_key=api_key)
    return await _call_llm(client, model, user_prompt)


def _parse_llm_response(response: str) -> RelevanceResult:
    """
    解析 LLM 的 JSON 响应。

    尝试多种解析方式：
    1. 直接 JSON 解析
    2. 从 markdown 代码块中提取 JSON
    3. 从文本中提取 JSON

    Args:
        response: LLM 返回的文本

    Returns:
        RelevanceResult
    """
    # 方法 1：直接 JSON 解析
    try:
        data = json.loads(response)
        memories = data.get("selected_memories", [])
        return RelevanceResult(selected_memories=memories, scores={})
    except json.JSONDecodeError:
        pass

    # 方法 2：从 ```json 代码块中提取
    import re
    json_pattern = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)
    match = json_pattern.search(response)
    if match:
        try:
            data = json.loads(match.group(1))
            memories = data.get("selected_memories", [])
            return RelevanceResult(selected_memories=memories, scores={})
        except json.JSONDecodeError:
            pass

    # 方法 3：尝试从文本中提取类似 JSON 的内容
    json_like_pattern = re.compile(r'\{[^{}]*"selected_memories"[^{}]*\}', re.DOTALL)
    match = json_like_pattern.search(response)
    if match:
        try:
            data = json.loads(match.group(0))
            memories = data.get("selected_memories", [])
            return RelevanceResult(selected_memories=memories, scores={})
        except json.JSONDecodeError:
            pass

    # 解析失败
    return RelevanceResult(selected_memories=[], scores={})


# =============================================================================
# 便捷函数
# =============================================================================

async def find_and_load_relevant_memories(
    query: str,
    memory_dir: str,
    llm_client: Any = None,
    model: str = "claude-sonnet-4-20250514",
) -> List[str]:
    """
    完整流程：扫描 → 检索 → 返回记忆内容。

    Args:
        query: 用户查询
        memory_dir: 记忆目录
        llm_client: LLM 客户端
        model: 模型

    Returns:
        相关记忆的正文内容列表
    """
    from memdir.scanner import scan_memory_files, format_memory_manifest, read_memory_content

    # 1. 扫描
    headers = await scan_memory_files(memory_dir)

    # 2. 格式化清单
    manifest = format_memory_manifest(headers)

    # 3. LLM 检索
    result = await find_relevant_memories(
        query=query,
        memory_manifest=manifest,
        llm_client=llm_client,
        model=model,
    )

    # 4. 读取选中记忆的内容
    contents = []
    filename_to_path = {h.filename: h.file_path for h in headers}

    for filename in result.selected_memories:
        if filename in filename_to_path:
            content = read_memory_content(filename_to_path[filename])
            contents.append(content)

    return contents
