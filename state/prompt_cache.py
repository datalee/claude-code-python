"""
System Prompt Sections - 系统提示词分块缓存

对应 Claude Code 源码: src/constants/systemPromptSections.ts

功能：
- 系统提示词分块管理
- 缓存固定节（只计算一次）
- 易失节每次重新计算
- 按需清除缓存
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# 类型别名
ComputeFn = Callable[[], str | None]


@dataclass
class SystemPromptSection:
    """
    系统提示词节。
    
    Attributes:
        name: 节名称
        compute: 计算函数
        cache_break: 是否破坏缓存（True 则每次重新计算）
    """
    name: str
    compute: ComputeFn
    cache_break: bool = False


@dataclass
class PromptSectionCache:
    """
    提示词节缓存。
    """
    entries: Dict[str, str] = field(default_factory=dict)
    timestamps: Dict[str, float] = field(default_factory=dict)


# 全局缓存实例
_cache: PromptSectionCache = PromptSectionCache()
_beta_header_latches: Dict[str, Any] = {}


def get_prompt_section_cache() -> PromptSectionCache:
    """获取提示词节缓存"""
    return _cache


def get_cache_entry(name: str) -> Optional[str]:
    """获取缓存条目"""
    return _cache.entries.get(name)


def set_cache_entry(name: str, value: str) -> None:
    """设置缓存条目"""
    _cache.entries[name] = value
    _cache.timestamps[name] = time.time()


def clear_cache_entry(name: str) -> None:
    """清除单个缓存条目"""
    if name in _cache.entries:
        del _cache.entries[name]
    if name in _cache.timestamps:
        del _cache.timestamps[name]


def clear_all_cache_entries() -> None:
    """清除所有缓存条目"""
    _cache.entries.clear()
    _cache.timestamps.clear()


def get_beta_header_latch(key: str) -> Optional[Any]:
    """获取 Beta header 闩锁"""
    return _beta_header_latches.get(key)


def set_beta_header_latch(key: str, value: Any) -> None:
    """设置 Beta header 闩锁"""
    _beta_header_latches[key] = value


def clear_beta_header_latches() -> None:
    """清除所有 Beta header 闩锁"""
    _beta_header_latches.clear()


# ============================================================================
# Section Factories
# ============================================================================

def system_prompt_section(
    name: str,
    compute: ComputeFn,
) -> SystemPromptSection:
    """
    创建缓存的系统提示词节。
    
    只计算一次，之后使用缓存值，直到被清除。
    
    Args:
        name: 节名称
        compute: 计算函数，返回提示词字符串
        
    Returns:
        SystemPromptSection 实例
    """
    return SystemPromptSection(
        name=name,
        compute=compute,
        cache_break=False,
    )


def uncached_system_prompt_section(
    name: str,
    compute: ComputeFn,
    reason: str = "",
) -> SystemPromptSection:
    """
    创建易失的系统提示词节。
    
    每次都会重新计算，会 BREAK 提示词缓存。
    需要提供原因说明。
    
    Args:
        name: 节名称
        compute: 计算函数
        reason: 为什么要打破缓存（必须提供）
        
    Returns:
        SystemPromptSection 实例
        
    Warning:
        这个节会破坏提示词缓存，只在必要时使用。
    """
    if not reason:
        raise ValueError(
            "uncached_system_prompt_section requires a reason explaining "
            "why this section must break the prompt cache"
        )
    
    return SystemPromptSection(
        name=name,
        compute=compute,
        cache_break=True,
    )


# ============================================================================
# Section Resolution
# ============================================================================

async def resolve_system_prompt_sections(
    sections: List[SystemPromptSection],
) -> List[Optional[str]]:
    """
    解析所有系统提示词节。
    
    对于 cache_break=False 的节，如果有缓存则使用缓存。
    对于 cache_break=True 的节，每次都重新计算。
    
    Args:
        sections: 系统提示词节列表
        
    Returns:
        解析后的提示词字符串列表
    """
    cache = get_prompt_section_cache()
    results: List[Optional[str]] = []
    
    for section in sections:
        if section.cache_break:
            # 易失节，每次计算
            value = section.compute()
            if value is not None:
                set_cache_entry(section.name, value)
            results.append(value)
        else:
            # 缓存节，先检查缓存
            cached = get_cache_entry(section.name)
            if cached is not None:
                results.append(cached)
            else:
                # 计算并缓存
                value = section.compute()
                if value is not None:
                    set_cache_entry(section.name, value)
                results.append(value)
    
    return results


def clear_system_prompt_sections() -> None:
    """
    清除所有系统提示词节状态。
    
    在 /clear 和 /compact 命令时调用。
    同时清除 beta header 闩锁，确保新对话使用新的评估值。
    """
    clear_all_cache_entries()
    clear_beta_header_latches()


# ============================================================================
# Utilities
# ============================================================================

def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计"""
    return {
        "entries": len(_cache.entries),
        "sections": list(_cache.entries.keys()),
        "timestamps": _cache.timestamps.copy(),
    }


def is_cached(name: str) -> bool:
    """检查某个节是否在缓存中"""
    return name in _cache.entries


__all__ = [
    "SystemPromptSection",
    "PromptSectionCache",
    "system_prompt_section",
    "uncached_system_prompt_section",
    "resolve_system_prompt_sections",
    "clear_system_prompt_sections",
    "get_prompt_section_cache",
    "get_cache_entry",
    "set_cache_entry",
    "clear_cache_entry",
    "clear_all_cache_entries",
    "get_cache_stats",
    "is_cached",
]
