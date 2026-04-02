"""
Components Layout - 布局组件

Stack, Grid, Sidebar, SplitView 等布局组件。
"""

from __future__ import annotations

from typing import Optional, List

from components.base import Component, ComponentProps


class Stack(Component):
    """堆叠布局组件"""

    def __init__(
        self,
        *children: Component,
        direction: str = "vertical",
        spacing: int = 1,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.direction = direction
        self.spacing = spacing
        self.children = list(children)

    def render(self) -> str:
        """渲染堆叠"""
        if self.direction == "horizontal":
            # 水平堆叠 - 所有内容在同一行
            parts = [child.render() for child in self.children]
            return " ".join(parts)
        else:
            # 垂直堆叠
            return "\n" * self.spacing.join(child.render() for child in self.children)


class HStack(Component):
    """水平堆叠组件"""

    def __init__(
        self,
        *children: Component,
        spacing: int = 1,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.spacing = spacing
        self.children = list(children)

    def render(self) -> str:
        """渲染水平布局"""
        parts = [child.render() for child in self.children]
        return " " * self.spacing.join(parts)


class VStack(Component):
    """垂直堆叠组件"""

    def __init__(
        self,
        *children: Component,
        spacing: int = 0,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.spacing = spacing
        self.children = list(children)

    def render(self) -> str:
        """渲染垂直布局"""
        sep = "\n" * (self.spacing + 1)
        return sep.join(child.render() for child in self.children)


class Grid(Component):
    """网格布局组件"""

    def __init__(
        self,
        *children: Component,
        columns: int = 2,
        gap: int = 1,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.columns = columns
        self.gap = gap
        self.children = list(children)

    def render(self) -> str:
        """渲染网格"""
        rows = []
        for i in range(0, len(self.children), self.columns):
            row_children = self.children[i:i + self.columns]
            rows.append(" ".join(child.render() for child in row_children))
        
        sep = "\n" * self.gap
        return sep.join(rows)


class Sidebar(Component):
    """侧边栏组件"""

    def __init__(
        self,
        sidebar_content: Component,
        main_content: Component,
        width: int = 30,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.sidebar = sidebar_content
        self.main = main_content
        self.width = width

    def render(self) -> str:
        """渲染侧边栏"""
        sidebar_lines = self.sidebar.render().split("\n")
        main_lines = self.main.render().split("\n")
        
        max_height = max(len(sidebar_lines), len(main_lines))
        
        # 补齐行数
        while len(sidebar_lines) < max_height:
            sidebar_lines.append("")
        while len(main_lines) < max_height:
            main_lines.append("")
        
        result = []
        for s, m in zip(sidebar_lines, main_lines):
            result.append(f"{s:<{self.width}}  {m}")
        
        return "\n".join(result)


class SplitView(Component):
    """分割视图组件"""

    def __init__(
        self,
        left: Component,
        right: Component,
        ratio: float = 0.5,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.left = left
        self.right = right
        self.ratio = ratio

    def render(self) -> str:
        """渲染分割视图"""
        left_lines = self.left.render().split("\n")
        right_lines = self.right.render().split("\n")
        
        max_height = max(len(left_lines), len(right_lines))
        
        while len(left_lines) < max_height:
            left_lines.append("")
        while len(right_lines) < max_height:
            right_lines.append("")
        
        left_width = int(80 * self.ratio)
        
        result = []
        for l, r in zip(left_lines, right_lines):
            result.append(f"{l:<{left_width}} │ {r}")
        
        return "\n".join(result)
