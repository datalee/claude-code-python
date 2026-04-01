"""
Ink Module - Interactive UI Framework

受 Ink (React for CLIs) 启发的交互式 UI 框架。
对应 Claude Code 源码: src/ink/*.ts

功能：
- 可更新的动态 UI（类似 React）
- 组件系统
- 实时输入处理
- 动画效果
"""

from __future__ import annotations

import asyncio
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# ============================================================================
# Ink Element 和 Component
# ============================================================================

class InkElement:
    """
    Ink 元素。
    
    所有 UI 组件的基类。
    """
    
    def __init__(self) -> None:
        self.children: List[InkElement] = []
        self.props: Dict[str, Any] = {}
        self.key: Optional[str] = None
    
    def render(self) -> str:
        """渲染元素"""
        return ""
    
    def mount(self, container: "InkContainer") -> None:
        """挂载到容器"""
        pass
    
    def unmount(self) -> None:
        """卸载"""
        pass


class InkText(InkElement):
    """文本元素"""
    
    def __init__(self, text: str = "", style: Optional[Dict[str, str]] = None) -> None:
        super().__init__()
        self.text = text
        self.style = style or {}
    
    def render(self) -> str:
        """渲染文本"""
        return self.text


class InkBox(InkElement):
    """盒子容器"""
    
    def __init__(
        self,
        *children: InkElement,
        border: Optional[str] = None,
        padding: int = 0,
        margin: int = 0,
        align: str = "left",
    ) -> None:
        super().__init__()
        self.children = list(children)
        self.border = border
        self.padding = padding
        self.margin = margin
        self.align = align
    
    def render(self) -> str:
        lines = []
        inner = self._render_children()
        if self.border:
            width = max(len(line) for line in inner.split("\n") or [""])
            lines.append(f"┌{'─' * (width + 2)}┐")
            for line in inner.split("\n"):
                lines.append(f"│ {line:<{width}} │")
            lines.append(f"└{'─' * (width + 2)}┘")
        else:
            lines.append(inner)
        return "\n".join(lines)
    
    def _render_children(self) -> str:
        return "\n".join(child.render() for child in self.children)


class InkDynamic(InkElement):
    """
    动态组件。
    
    每次渲染时重新计算值。
    """
    
    def __init__(self, render_fn: Callable[[], str]) -> None:
        super().__init__()
        self.render_fn = render_fn
    
    def render(self) -> str:
        return self.render_fn()


class InkSpinner(InkElement):
    """旋转动画"""
    
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    
    def __init__(self, text: str = "Loading") -> None:
        super().__init__()
        self.text = text
        self.frame = 0
    
    def tick(self) -> None:
        """更新帧"""
        self.frame = (self.frame + 1) % len(self.FRAMES)
    
    def render(self) -> str:
        return f"{self.FRAMES[self.frame]} {self.text}"


class InkProgress(InkElement):
    """进度条"""
    
    def __init__(
        self,
        value: float = 0,
        total: float = 100,
        label: str = "",
        width: int = 20,
    ) -> None:
        super().__init__()
        self.value = value
        self.total = total
        self.label = label
        self.width = width
    
    def set_progress(self, value: float, total: Optional[float] = None) -> None:
        """设置进度"""
        self.value = value
        if total is not None:
            self.total = total
    
    def render(self) -> str:
        percent = min(100, (self.value / self.total * 100)) if self.total > 0 else 0
        filled = int(self.width * self.value / self.total) if self.total > 0 else 0
        empty = self.width - filled
        bar = "█" * filled + "░" * empty
        label = f"{self.label} " if self.label else ""
        return f"{label}|{bar}| {percent:.0f}%"


class InkTable(InkElement):
    """表格"""
    
    def __init__(
        self,
        headers: List[str],
        rows: List[List[str]],
        column_widths: Optional[List[int]] = None,
    ) -> None:
        super().__init__()
        self.headers = headers
        self.rows = rows
        self.column_widths = column_widths
    
    def render(self) -> str:
        if not self.column_widths:
            max_width = 80
            avail = max_width - len(self.headers) * 3 - 2
            cw = avail // len(self.headers)
            self.column_widths = [cw] * len(self.headers)
        
        lines = []
        
        # 表头
        header_line = "│ " + " │ ".join(
            h[:w].ljust(w) for h, w in zip(self.headers, self.column_widths)
        ) + " │"
        lines.append(header_line)
        
        # 分隔
        sep = "├" + "┼".join("─" * (w + 2) for w in self.column_widths) + "┤"
        lines.append(sep)
        
        # 数据行
        for row in self.rows:
            row_line = "│ " + " │ ".join(
                str(cell)[:w].ljust(w) for cell, w in zip(row, self.column_widths)
            ) + " │"
            lines.append(row_line)
        
        return "\n".join(lines)


# ============================================================================
# InkContainer
# ============================================================================

class InkContainer:
    """
    Ink 容器。
    
    管理一组 InkElement 的渲染和更新。
    """
    
    def __init__(self, output: Optional[Any] = None) -> None:
        self.output = output or sys.stdout
        self.elements: Dict[str, InkElement] = {}
        self._render_count = 0
    
    def add(self, key: str, element: InkElement) -> None:
        """添加元素"""
        self.elements[key] = element
        element.mount(self)
    
    def remove(self, key: str) -> None:
        """移除元素"""
        if key in self.elements:
            self.elements[key].unmount()
            del self.elements[key]
    
    def get(self, key: str) -> Optional[InkElement]:
        """获取元素"""
        return self.elements.get(key)
    
    def render(self) -> None:
        """渲染所有元素"""
        self._render_count += 1
        output_lines = []
        
        for key, element in self.elements.items():
            rendered = element.render()
            if rendered:
                output_lines.append(rendered)
        
        # 清除屏幕并重新绘制
        output = "\n\n".join(output_lines)
        clear = "\033[2J\033[H"
        self.output.write(f"{clear}{output}\n")
        self.output.flush()
    
    def render_once(self) -> None:
        """单次渲染（不清屏）"""
        output_lines = []
        for key, element in self.elements.items():
            rendered = element.render()
            if rendered:
                output_lines.append(rendered)
        self.output.write("\n\n".join(output_lines) + "\n")
        self.output.flush()


# ============================================================================
# InkApp - 完整应用框架
# ============================================================================

@dataclass
class InkAppState:
    """应用状态"""
    value: Dict[str, Any] = field(default_factory=dict)
    
    def get(self, key: str, default: Any = None) -> Any:
        return self.value.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        self.value[key] = value


class InkApp:
    """
    Ink 应用。
    
    提供完整的状态管理和重渲染机制。
    """
    
    def __init__(
        self,
        initial_state: Optional[Dict[str, Any]] = None,
        output: Optional[Any] = None,
    ) -> None:
        self.state = InkAppState(value=initial_state or {})
        self.container = InkContainer(output=output)
        self._running = False
        self._components: Dict[str, Callable[[], InkElement]] = {}
    
    def component(self, key: str) -> Callable:
        """装饰器：注册组件"""
        def decorator(fn: Callable[[], InkElement]) -> Callable:
            self._components[key] = fn
            return fn
        return decorator
    
    def set_state(self, updates: Dict[str, Any]) -> None:
        """更新状态"""
        for key, value in updates.items():
            self.state.set(key, value)
        self.rerender()
    
    def rerender(self) -> None:
        """重新渲染所有组件"""
        for key, fn in self._components.items():
            element = fn()
            existing = self.container.get(key)
            if existing:
                self.container.remove(key)
            self.container.add(key, element)
        self.container.render()
    
    async def run(self) -> None:
        """运行应用"""
        self._running = True
        self.rerender()
        
        while self._running:
            await asyncio.sleep(0.1)
    
    def stop(self) -> None:
        """停止应用"""
        self._running = False


# ============================================================================
# ANSI 颜色助手
# ============================================================================

class ANSI:
    """ANSI 转义码"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"
    
    @classmethod
    def clear_screen(cls) -> str:
        return "\033[2J\033[H"
    
    @classmethod
    def hide_cursor(cls) -> str:
        return "\033[?25l"
    
    @classmethod
    def show_cursor(cls) -> str:
        return "\033[?25h"
    
    @classmethod
    def move_to(cls, row: int, col: int) -> str:
        return f"\033[{row};{col}H"
    
    @classmethod
    def strip(cls, text: str) -> str:
        """移除 ANSI 序列"""
        import re
        return re.sub(r"\x1b\[[0-9;]*m", "", text)


# ============================================================================
# 全局实例
# ============================================================================

_app: Optional[InkApp] = None


def create_app(initial_state: Optional[Dict[str, Any]] = None) -> InkApp:
    """创建 Ink 应用"""
    global _app
    _app = InkApp(initial_state=initial_state)
    return _app


def get_app() -> Optional[InkApp]:
    """获取当前应用"""
    return _app


__all__ = [
    # 元素
    "InkElement",
    "InkText",
    "InkBox",
    "InkDynamic",
    "InkSpinner",
    "InkProgress",
    "InkTable",
    # 容器和应用
    "InkContainer",
    "InkAppState",
    "InkApp",
    # 工具
    "ANSI",
    "create_app",
    "get_app",
]
