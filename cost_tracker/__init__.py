"""
Cost Tracker - Token 消耗追踪与成本统计

追踪 API 调用、Token 消耗、成本统计。
对应 Claude Code 源码: src/cost-tracker.ts

功能：
1. 追踪每次 API 调用的消耗（input/output/cache tokens）
2. 按模型分类统计
3. 格式化成本展示
4. 会话间状态保存与恢复
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

# =============================================================================
# 定价常量（参考 Anthropic 官方定价）
# =============================================================================

# 每百万 Token 的价格（美元）
MODEL_PRICING_PER_MILLION = {
    # Claude 4 系列
    "claude-opus-4-5": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-5": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5": {"input": 0.8, "output": 4.0},
    # Claude 3.5 系列
    "claude-opus-3.5": {"input": 15.0, "output": 75.0},
    "claude-sonnet-3.5": {"input": 3.0, "output": 15.0},
    "claude-haiku-3.5": {"input": 0.8, "output": 4.0},
    # Claude 3 系列
    "claude-opus-3": {"input": 15.0, "output": 75.0},
    "claude-sonnet-3": {"input": 3.0, "output": 15.0},
    "claude-haiku-3": {"input": 0.25, "output": 1.25},
    # Claude 2.x
    "claude-2.1": {"input": 8.0, "output": 24.0},
    "claude-2.0": {"input": 8.0, "output": 24.0},
    # Claude 1.x
    "claude-instant-1": {"input": 0.8, "output": 2.4},
    # 默认（如果模型不在列表中）
    "default": {"input": 3.0, "output": 15.0},
}

# Cache pricing (通常有折扣)
CACHE_READ_PRICING_PER_MILLION = 0.08  # $0.08/M cache read (90% off)
CACHE_WRITE_PRICING_PER_MILLION = 3.75  # $3.75/M cache write (75% off, approximated)


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class ModelUsage:
    """单个模型的 usage"""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    web_search_requests: int = 0
    cost_usd: float = 0.0
    api_calls: int = 0


@dataclass
class SessionCost:
    """会话成本快照"""
    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cache_creation_tokens: int = 0
    total_lines_added: int = 0
    total_lines_removed: int = 0
    total_api_duration_ms: float = 0.0  # API 调用耗时
    total_wall_duration_ms: float = 0.0  # 墙上时间
    model_usage: Dict[str, ModelUsage] = field(default_factory=dict)
    has_unknown_model: bool = False


@dataclass
class StoredCostState:
    """持久化存储的成本状态"""
    total_cost_usd: float
    total_api_duration: float
    total_api_duration_without_retries: float
    total_tool_duration: float
    total_lines_added: int
    total_lines_removed: int
    last_duration: Optional[float]
    model_usage: Optional[Dict[str, ModelUsage]]


# =============================================================================
# 成本计算
# =============================================================================

def calculate_usd_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
) -> float:
    """
    计算 API 调用的美元成本。

    Args:
        model: 模型名称
        input_tokens: 输入 token 数
        output_tokens: 输出 token 数
        cache_read_tokens: 缓存读取 token 数
        cache_creation_tokens: 缓存创建 token 数

    Returns:
        美元成本
    """
    # 归一化模型名
    normalized = _normalize_model_name(model)

    # 查找定价
    pricing = MODEL_PRICING_PER_MILLION.get(normalized, MODEL_PRICING_PER_MILLION["default"])

    # 计算成本
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]

    # Cache 成本
    cache_read_cost = (cache_read_tokens / 1_000_000) * CACHE_READ_PRICING_PER_MILLION
    cache_creation_cost = (cache_creation_tokens / 1_000_000) * CACHE_WRITE_PRICING_PER_MILLION

    total = input_cost + output_cost + cache_read_cost + cache_creation_cost

    return round(total, 6)


def _normalize_model_name(model: str) -> str:
    """归一化模型名称，提取 key 部分"""
    # 例如 "claude-sonnet-4-20250514" -> "claude-sonnet-4"
    model = model.lower()

    # 常见模式
    for key in MODEL_PRICING_PER_MILLION:
        if key in model:
            return key

    return "default"


def _format_model_short_name(model: str) -> str:
    """获取模型简称"""
    # 去除日期后缀
    parts = model.split("-")
    if len(parts) >= 4 and parts[-1].isdigit():
        parts = parts[:-1]

    name = "-".join(parts)

    # 进一步简化
    if "sonnet" in name.lower():
        return "Sonnet"
    if "opus" in name.lower():
        return "Opus"
    if "haiku" in name.lower():
        return "Haiku"

    return name


# =============================================================================
# 格式化输出
# =============================================================================

def format_cost(cost: float, max_decimal_places: int = 4) -> str:
    """
    格式化成本为字符串。

    Args:
        cost: 成本（美元）
        max_decimal_places: 最大小数位数

    Returns:
        格式化的字符串，如 "$0.0012" 或 "$1.23"
    """
    if cost > 0.5:
        return f"${round(cost, 2):.2f}"
    return f"${cost:.{max_decimal_places}f}"


def format_number(n: int) -> str:
    """格式化数字，添加千分位分隔符"""
    return f"{n:,}"


def format_duration(ms: float) -> str:
    """
    格式化时长。

    Args:
        ms: 毫秒数

    Returns:
        格式化的字符串，如 "1m 23s" 或 "45.2s"
    """
    if ms < 1000:
        return f"{ms:.0f}ms"

    seconds = ms / 1000
    if seconds < 60:
        return f"{seconds:.1f}s"

    minutes = int(seconds // 60)
    remaining_seconds = seconds % 60
    if remaining_seconds < 1:
        return f"{minutes}m"
    return f"{minutes}m {remaining_seconds:.0f}s"


def format_model_usage_line(usage: ModelUsage, model_short: str) -> str:
    """
    格式化单个模型的 usage 行。

    Example:
        Sonnet:  1,234 input, 5,678 output, 90 cache read, 10 cache write ($0.42)
    """
    parts = [
        f"{format_number(usage.input_tokens)} input",
        f"{format_number(usage.output_tokens)} output",
    ]

    if usage.cache_read_input_tokens > 0:
        parts.append(f"{format_number(usage.cache_read_input_tokens)} cache read")

    if usage.cache_creation_input_tokens > 0:
        parts.append(f"{format_number(usage.cache_creation_input_tokens)} cache write")

    if usage.web_search_requests > 0:
        parts.append(f"{format_number(usage.web_search_requests)} web search")

    cost_str = f" ({format_cost(usage.cost_usd)})" if usage.cost_usd > 0 else ""

    return f"{model_short}: " + ", ".join(parts) + cost_str


def format_total_cost(state: SessionCost) -> str:
    """
    格式化完整的成本报告。

    Returns:
        多行成本报告字符串
    """
    lines = []

    # 总成本
    cost_display = format_cost(state.total_cost_usd)
    if state.has_unknown_model:
        cost_display += " (costs may be inaccurate)"

    lines.append(f"Total cost:           {cost_display}")
    lines.append(f"Total duration (API): {format_duration(state.total_api_duration_ms)}")
    lines.append(f"Total duration (wall): {format_duration(state.total_wall_duration_ms)}")

    # 代码变化
    lines.append(
        f"Total code changes:   "
        f"{state.total_lines_added} {'line' if state.total_lines_added == 1 else 'lines'} added, "
        f"{state.total_lines_removed} {'line' if state.total_lines_removed == 1 else 'lines'} removed"
    )

    # 按模型分组的 usage
    if state.model_usage:
        lines.append("")
        lines.append("Usage by model:")

        for model, usage in state.model_usage.items():
            short = _format_model_short_name(model)
            line = format_model_usage_line(usage, short)
            lines.append(line)

    return "\n".join(lines)


# =============================================================================
# 全局状态管理
# =============================================================================

class CostTracker:
    """
    全局成本追踪器。

    这是一个单例，负责追踪整个会话的成本。
    """

    _instance: Optional["CostTracker"] = None

    def __new__(cls) -> "CostTracker":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._reset()
        return cls._instance

    def _reset(self) -> None:
        """重置所有状态"""
        self._total_cost: float = 0.0
        self._total_input_tokens: int = 0
        self._total_output_tokens: int = 0
        self._total_cache_read_tokens: int = 0
        self._total_cache_creation_tokens: int = 0
        self._total_lines_added: int = 0
        self._total_lines_removed: int = 0
        self._total_api_duration_ms: float = 0.0
        self._total_wall_duration_ms: float = 0.0
        self._model_usage: Dict[str, ModelUsage] = {}
        self._has_unknown_model: bool = False
        self._session_start_time: float = time.time()

    def add_api_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
        api_duration_ms: float = 0.0,
    ) -> float:
        """
        记录一次 API 调用。

        Args:
            model: 模型名称
            input_tokens: 输入 token 数
            output_tokens: 输出 token 数
            cache_read_tokens: 缓存读取 token 数
            cache_creation_tokens: 缓存创建 token 数
            api_duration_ms: API 调用耗时（毫秒）

        Returns:
            本次调用的美元成本
        """
        # 计算成本
        cost = calculate_usd_cost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_creation_tokens=cache_creation_tokens,
        )

        # 更新总量
        self._total_cost += cost
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        self._total_cache_read_tokens += cache_read_tokens
        self._total_cache_creation_tokens += cache_creation_tokens
        self._total_api_duration_ms += api_duration_ms

        # 更新模型分项
        if model not in self._model_usage:
            self._model_usage[model] = ModelUsage()

        usage = self._model_usage[model]
        usage.input_tokens += input_tokens
        usage.output_tokens += output_tokens
        usage.cache_read_input_tokens += cache_read_tokens
        usage.cache_creation_input_tokens += cache_creation_tokens
        usage.cost_usd += cost
        usage.api_calls += 1

        # 检查是否未知模型
        if _normalize_model_name(model) == "default":
            self._has_unknown_model = True

        return cost

    def add_lines_changed(self, added: int, removed: int) -> None:
        """记录代码变化"""
        self._total_lines_added += added
        self._total_lines_removed += removed

    def add_web_search(self, model: str, count: int = 1) -> None:
        """记录 web search 请求"""
        if model not in self._model_usage:
            self._model_usage[model] = ModelUsage()
        self._model_usage[model].web_search_requests += count

    def update_wall_duration(self) -> None:
        """更新墙上时间"""
        self._total_wall_duration_ms = (time.time() - self._session_start_time) * 1000

    def get_state(self) -> SessionCost:
        """获取当前状态快照"""
        self.update_wall_duration()
        return SessionCost(
            total_cost_usd=self._total_cost,
            total_input_tokens=self._total_input_tokens,
            total_output_tokens=self._total_output_tokens,
            total_cache_read_tokens=self._total_cache_read_tokens,
            total_cache_creation_tokens=self._total_cache_creation_tokens,
            total_lines_added=self._total_lines_added,
            total_lines_removed=self._total_lines_removed,
            total_api_duration_ms=self._total_api_duration_ms,
            total_wall_duration_ms=self._total_wall_duration_ms,
            model_usage=dict(self._model_usage),
            has_unknown_model=self._has_unknown_model,
        )

    def get_total_cost(self) -> float:
        """获取总成本（美元）"""
        return self._total_cost

    def get_model_usage(self) -> Dict[str, ModelUsage]:
        """获取按模型分组的 usage"""
        return dict(self._model_usage)

    def has_unknown_model_cost(self) -> bool:
        """是否有未知模型的成本（可能不准确）"""
        return self._has_unknown_model

    def reset(self) -> None:
        """重置所有状态（新会话）"""
        self._reset()

    def restore(self, state: StoredCostState) -> None:
        """
        从持久化状态恢复。

        Args:
            state: 之前保存的状态
        """
        self._total_cost = state.total_cost_usd
        self._total_api_duration_ms = state.total_api_duration
        self._total_lines_added = state.total_lines_added
        self._total_lines_removed = state.total_lines_removed

        if state.model_usage:
            self._model_usage = dict(state.model_usage)

    def to_stored_state(self) -> StoredCostState:
        """转换为可持久化的状态"""
        return StoredCostState(
            total_cost_usd=self._total_cost,
            total_api_duration=self._total_api_duration_ms,
            total_api_duration_without_retries=self._total_api_duration_ms,
            total_tool_duration=0.0,
            total_lines_added=self._total_lines_added,
            total_lines_removed=self._total_lines_removed,
            last_duration=self._total_wall_duration_ms,
            model_usage=dict(self._model_usage) if self._model_usage else None,
        )


# =============================================================================
# 全局单例访问函数
# =============================================================================

def get_cost_tracker() -> CostTracker:
    """获取全局 CostTracker 单例"""
    return CostTracker()


# 便捷函数（与 TypeScript 源码的导出对应）
def get_total_cost_usd() -> float:
    """获取总成本"""
    return get_cost_tracker().get_total_cost()


def get_total_input_tokens() -> int:
    """获取总输入 tokens"""
    return get_cost_tracker().get_state().total_input_tokens


def get_total_output_tokens() -> int:
    """获取总输出 tokens"""
    return get_cost_tracker().get_state().total_output_tokens


def get_total_cache_read_tokens() -> int:
    """获取总 cache read tokens"""
    return get_cost_tracker().get_state().total_cache_read_tokens


def get_total_cache_creation_tokens() -> int:
    """获取总 cache creation tokens"""
    return get_cost_tracker().get_state().total_cache_creation_tokens


def get_total_lines_added() -> int:
    """获取总添加行数"""
    return get_cost_tracker().get_state().total_lines_added


def get_total_lines_removed() -> int:
    """获取总删除行数"""
    return get_cost_tracker().get_state().total_lines_removed


def get_total_api_duration() -> float:
    """获取总 API 调用耗时（毫秒）"""
    return get_cost_tracker().get_state().total_api_duration_ms


def get_total_duration() -> float:
    """获取总墙上时间（毫秒）"""
    return get_cost_tracker().get_state().total_wall_duration_ms


def get_model_usage() -> Dict[str, ModelUsage]:
    """获取按模型分组的 usage"""
    return get_cost_tracker().get_model_usage()


def format_cost_display() -> str:
    """获取格式化的成本报告"""
    return format_total_cost(get_cost_tracker().get_state())
