"""
Components Base - 基础组件

所有 UI 组件的基类。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable


@dataclass
class ComponentProps:
    """组件属性基类"""
    style: Optional[Dict[str, Any]] = None
    class_name: Optional[str] = None
    id: Optional[str] = None
    on_click: Optional[Callable] = None
    on_change: Optional[Callable] = None
    children: List["Component"] = field(default_factory=list)


class Component(ABC):
    """
    UI 组件基类。
    
    所有组件必须继承此类并实现 render() 方法。
    """

    def __init__(self, props: Optional[ComponentProps] = None) -> None:
        self.props = props or ComponentProps()
        self.children = self.props.children or []

    @abstractmethod
    def render(self) -> str:
        """渲染组件为字符串"""
        ...

    def add_child(self, child: "Component") -> None:
        """添加子组件"""
        self.children.append(child)

    def __str__(self) -> str:
        return self.render()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"


class BaseText(Component):
    """基础文本组件"""

    def __init__(
        self,
        text: str = "",
        bold: bool = False,
        italic: bool = False,
        color: Optional[str] = None,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.text = text
        self.bold = bold
        self.italic = italic
        self.color = color

    def render(self) -> str:
        """渲染文本"""
        result = self.text
        
        if self.bold:
            result = f"\033[1m{result}\033[0m"
        if self.italic:
            result = f"\033[3m{result}\033[0m"
        
        return result


class BaseBox(Component):
    """基础盒子组件"""

    def __init__(
        self,
        *children: Component,
        border: bool = False,
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
            lines = inner.split("\n")
            width = max(len(line) for line in lines) if lines else 0
            top = "┌" + "─" * (width + 2) + "┐"
            bottom = "└" + "─" * (width + 2) + "┘"
            
            result = [top]
            for line in lines:
                result.append(f"│ {line:<{width}} │")
            result.append(bottom)
            return "\n".join(result)
        
        return inner


class BaseSpinner(Component):
    """基础旋转动画组件"""

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
        return f"{self.FRAMES[self.frame]} {self.text}"
