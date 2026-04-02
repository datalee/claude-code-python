"""
Components Feedback - 反馈组件

Toast, Modal, Alert, Progress, Skeleton 等反馈组件。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List

from components.base import Component, ComponentProps


class Toast(Component):
    """提示消息组件"""

    def __init__(
        self,
        message: str = "",
        type: str = "info",
        duration: int = 3000,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.message = message
        self.type = type
        self.duration = duration

    def render(self) -> str:
        """渲染提示"""
        icons = {
            "success": "✓",
            "error": "✗",
            "warning": "⚠",
            "info": "ℹ",
        }
        icon = icons.get(self.type, "ℹ")
        return f"[{icon}] {self.message}"


class Modal(Component):
    """模态框组件"""

    def __init__(
        self,
        title: str = "",
        content: str = "",
        buttons: Optional[List[str]] = None,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.title = title
        self.content = content
        self.buttons = buttons or ["OK"]

    def render(self) -> str:
        """渲染模态框"""
        width = max(len(self.title), len(self.content), 30)
        
        lines = [
            "┌" + "─" * (width + 2) + "┐",
            f"│ {self.title:<{width}} │",
            "├" + "─" * (width + 2) + "┤",
            f"│ {self.content:<{width}} │",
            "├" + "─" * (width + 2) + "┤",
        ]

        # 按钮
        btn_str = " ".join(f"[{b}]" for b in self.buttons)
        lines.append(f"│ {btn_str:<{width}} │")
        lines.append("└" + "─" * (width + 2) + "┘")

        return "\n".join(lines)


class Alert(Component):
    """警告提示组件"""

    def __init__(
        self,
        message: str = "",
        type: str = "info",
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.message = message
        self.type = type

    def render(self) -> str:
        """渲染警告"""
        icons = {
            "success": "✅",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️",
        }
        icon = icons.get(self.type, "ℹ️")
        
        lines = [f"{icon} {self.message}"]
        
        if self.type == "error":
            lines.append("Please fix the issue above.")
        elif self.type == "warning":
            lines.append("Please take note of this warning.")
        
        return "\n".join(lines)


class Progress(Component):
    """进度条组件"""

    def __init__(
        self,
        value: float = 0,
        total: float = 100,
        label: str = "",
        width: int = 30,
        show_percent: bool = True,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.value = value
        self.total = total
        self.label = label
        self.width = width
        self.show_percent = show_percent

    def render(self) -> str:
        """渲染进度条"""
        percent = min(100, (self.value / self.total * 100)) if self.total > 0 else 0
        filled = int(self.width * self.value / self.total) if self.total > 0 else 0
        empty = self.width - filled

        bar = "█" * filled + "░" * empty
        label_str = f"{self.label} " if self.label else ""
        percent_str = f" {percent:.0f}%" if self.show_percent else ""

        return f"{label_str}│{bar}│{percent_str}"


class Skeleton(Component):
    """骨架屏组件"""

    def __init__(
        self,
        lines: int = 3,
        width: int = 40,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.lines = lines
        self.width = width

    def render(self) -> str:
        """渲染骨架屏"""
        skeleton_chars = "▒░▒░▒"
        lines = []
        
        for i in range(self.lines):
            w = self.width - (i % 3) * 5
            lines.append(skeleton_chars[:w])
        
        return "\n".join(lines)
