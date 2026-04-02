"""
Components Display - 展示组件

Table, List, Card 等展示组件。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, List

from components.base import Component, ComponentProps


class Table(Component):
    """表格组件"""

    def __init__(
        self,
        headers: List[str] = None,
        rows: List[List[str]] = None,
        column_widths: Optional[List[int]] = None,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.headers = headers or []
        self.rows = rows or []
        self.column_widths = column_widths or []

    def render(self) -> str:
        """渲染表格"""
        if not self.column_widths:
            max_width = 80
            avail = max_width - len(self.headers) * 3 - 2
            cw = avail // len(self.headers) if self.headers else 10
            self.column_widths = [cw] * len(self.headers)

        lines = []

        # 表头
        if self.headers:
            header_line = "│ " + " │ ".join(
                h[:w].ljust(w) for h, w in zip(self.headers, self.column_widths)
            ) + " │"
            lines.append(header_line)

            # 分隔线
            sep = "├" + "┼".join("─" * (w + 2) for w in self.column_widths) + "┤"
            lines.append(sep)

        # 数据行
        for row in self.rows:
            row_line = "│ " + " │ ".join(
                str(cell)[:w].ljust(w) for cell, w in zip(row, self.column_widths)
            ) + " │"
            lines.append(row_line)

        # 底边框
        if self.headers or self.rows:
            bottom = "└" + "┴".join("─" * (w + 2) for w in self.column_widths) + "┘"
            lines.append(bottom)

        return "\n".join(lines)


class ListItem(Component):
    """列表项组件"""

    def __init__(
        self,
        text: str = "",
        icon: str = "•",
        depth: int = 0,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.text = text
        self.icon = icon
        self.depth = depth

    def render(self) -> str:
        """渲染列表项"""
        indent = "  " * self.depth
        return f"{indent}{self.icon} {self.text}"


class List(Component):
    """列表组件"""

    def __init__(
        self,
        *items: str,
        ordered: bool = False,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.items = list(items)
        self.ordered = ordered

    def render(self) -> str:
        """渲染列表"""
        lines = []
        for i, item in enumerate(self.items, 1):
            if self.ordered:
                lines.append(f"  {i}. {item}")
            else:
                lines.append(f"  • {item}")
        return "\n".join(lines)


class CardHeader(Component):
    """卡片头部组件"""

    def __init__(
        self,
        title: str = "",
        subtitle: Optional[str] = None,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.title = title
        self.subtitle = subtitle

    def render(self) -> str:
        """渲染卡片头部"""
        lines = [f"\033[1m{self.title}\033[0m"]
        if self.subtitle:
            lines.append(f"\033[2m{self.subtitle}\033[0m")
        return "\n".join(lines)


class CardBody(Component):
    """卡片内容组件"""

    def __init__(
        self,
        *children: Component,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.children = list(children)

    def render(self) -> str:
        """渲染卡片内容"""
        return "\n".join(child.render() for child in self.children)


class Card(Component):
    """卡片组件"""

    def __init__(
        self,
        header: Optional[Component] = None,
        body: Optional[Component] = None,
        border: bool = True,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.header = header
        self.body = body
        self.border = border

    def render(self) -> str:
        """渲染卡片"""
        parts = []

        if self.header:
            parts.append(self.header.render())

        if self.body:
            parts.append(self.body.render())

        if self.border:
            inner = "\n".join(parts)
            lines = inner.split("\n")
            width = max(len(line) for line in lines) if lines else 0

            top = "┌" + "─" * (width + 2) + "┐"
            bottom = "└" + "─" * (width + 2) + "┘"

            result = [top]
            for line in lines:
                result.append(f"│ {line:<{width}} │")
            result.append(bottom)
            return "\n".join(result)

        return "\n".join(parts)
