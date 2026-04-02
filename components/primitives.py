"""
Components Primitives - 基础 UI 组件

Text, Box, Spinner, Divider, Badge, Tag 等基础组件。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from components.base import Component, ComponentProps


# 颜色映射
COLORS = {
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "reset": "\033[0m",
}

STYLES = {
    "bold": "\033[1m",
    "dim": "\033[2m",
    "italic": "\033[3m",
    "underline": "\033[4m",
    "reset": "\033[0m",
}


def _style(text: str, styles: list) -> str:
    """应用样式"""
    result = text
    for s in styles:
        if s in STYLES:
            result = STYLES[s] + result
    result += STYLES["reset"]
    return result


def _color(text: str, color: str) -> str:
    """应用颜色"""
    if color in COLORS:
        return COLORS[color] + text + COLORS["reset"]
    return text


class Text(Component):
    """文本组件"""

    def __init__(
        self,
        text: str = "",
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        color: Optional[str] = None,
        bg: Optional[str] = None,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.text = text
        self.bold = bold
        self.italic = italic
        self.underline = underline
        self.color = color
        self.bg = bg

    def render(self) -> str:
        """渲染文本"""
        styles = []
        if self.bold:
            styles.append("bold")
        if self.italic:
            styles.append("italic")
        if self.underline:
            styles.append("underline")
        
        result = _style(self.text, styles)
        
        if self.color:
            result = _color(result, self.color)
        
        return result


class Box(Component):
    """盒子容器组件"""

    def __init__(
        self,
        *children: Component,
        border: str = "",
        padding: int = 0,
        margin: int = 0,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.border = border
        self.padding = padding
        self.margin = margin
        self.children = list(children)

    def render(self) -> str:
        """渲染盒子"""
        inner = "\n".join(child.render() for child in self.children)
        
        if self.border:
            lines = inner.split("\n") if inner else [""]
            width = max(len(line) for line in lines)
            
            if self.border == "round":
                top = "╭" + "─" * (width + 2) + "╮"
                bottom = "╰" + "─" * (width + 2) + "╯"
                v = "│"
            else:
                top = "┌" + "─" * (width + 2) + "┐"
                bottom = "└" + "─" * (width + 2) + "┘"
                v = "│"
            
            result = [top]
            for line in lines:
                result.append(f"{v} {line:<{width}} {v}")
            result.append(bottom)
            return "\n".join(result)
        
        return inner


class Spinner(Component):
    """旋转动画组件"""

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(
        self,
        text: str = "Loading",
        color: Optional[str] = None,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.text = text
        self.color = color
        self.frame = 0

    def tick(self) -> None:
        """更新动画帧"""
        self.frame = (self.frame + 1) % len(self.FRAMES)

    def render(self) -> str:
        """渲染当前帧"""
        result = f"{self.FRAMES[self.frame]} {self.text}"
        if self.color:
            result = _color(result, self.color)
        return result


class Divider(Component):
    """分隔线组件"""

    def __init__(
        self,
        char: str = "─",
        color: Optional[str] = None,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.char = char
        self.color = color

    def render(self) -> str:
        """渲染分隔线"""
        line = self.char * 40
        if self.color:
            return _color(line, self.color)
        return line


class Badge(Component):
    """徽章组件"""

    def __init__(
        self,
        text: str = "",
        color: str = "blue",
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.text = text
        self.color = color

    def render(self) -> str:
        """渲染徽章"""
        return _color(f"[{self.text}]", self.color)


class Tag(Component):
    """标签组件"""

    def __init__(
        self,
        text: str = "",
        color: Optional[str] = None,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.text = text
        self.color = color

    def render(self) -> str:
        """渲染标签"""
        result = f"<{self.text}>"
        if self.color:
            result = _color(result, self.color)
        return result
