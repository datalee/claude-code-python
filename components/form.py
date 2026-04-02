"""
Components Form - 表单组件

Button, Input, Select, Checkbox, Radio, Switch 等表单组件。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, List

from components.base import Component, ComponentProps


class Button(Component):
    """按钮组件"""

    def __init__(
        self,
        text: str = "",
        variant: str = "default",
        size: str = "medium",
        disabled: bool = False,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.text = text
        self.variant = variant
        self.size = size
        self.disabled = disabled

    def render(self) -> str:
        """渲染按钮"""
        if self.disabled:
            return f"[{self.text}] (disabled)"
        
        prefix = {
            "primary": "▶ ",
            "default": "○ ",
            "danger": "⚠ ",
            "success": "✓ ",
        }.get(self.variant, "")
        
        return f"[{prefix}{self.text}]"


class Input(Component):
    """输入框组件"""

    def __init__(
        self,
        placeholder: str = "",
        value: str = "",
        type: str = "text",
        disabled: bool = False,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.placeholder = placeholder
        self.value = value
        self.type = type
        self.disabled = disabled

    def render(self) -> str:
        """渲染输入框"""
        display = self.value or self.placeholder
        if not self.value and self.placeholder:
            display = f"{self.placeholder}_"
        
        width = max(len(display), 20)
        return f"┌{'─' * width}┐\n│ {display:<{width}} │\n└{'─' * width}┘"


class Select(Component):
    """选择框组件"""

    def __init__(
        self,
        options: List[str] = None,
        selected: Optional[int] = None,
        placeholder: str = "Select...",
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.options = options or []
        self.selected = selected
        self.placeholder = placeholder

    def render(self) -> str:
        """渲染选择框"""
        if not self.options:
            return f"[{self.placeholder}]"
        
        lines = [f"┌{'─' * 30}┐"]
        for i, opt in enumerate(self.options):
            marker = "●" if i == self.selected else " "
            lines.append(f"│ {marker} {opt:<27} │")
        lines.append(f"└{'─' * 30}┘")
        return "\n".join(lines)


class Checkbox(Component):
    """复选框组件"""

    def __init__(
        self,
        label: str = "",
        checked: bool = False,
        disabled: bool = False,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.label = label
        self.checked = checked
        self.disabled = disabled

    def render(self) -> str:
        """渲染复选框"""
        marker = "[x]" if self.checked else "[ ]"
        if self.disabled:
            return f"{marker} {label} (disabled)"
        return f"{marker} {self.label}"


class Radio(Component):
    """单选框组件"""

    def __init__(
        self,
        label: str = "",
        selected: bool = False,
        disabled: bool = False,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.label = label
        self.selected = selected
        self.disabled = disabled

    def render(self) -> str:
        """渲染单选框"""
        marker = "(●)" if self.selected else "( )"
        if self.disabled:
            return f"{marker} {self.label} (disabled)"
        return f"{marker} {self.label}"


class Switch(Component):
    """开关组件"""

    def __init__(
        self,
        label: str = "",
        on: bool = False,
        disabled: bool = False,
        props: Optional[ComponentProps] = None,
    ) -> None:
        super().__init__(props)
        self.label = label
        self.on = on
        self.disabled = disabled

    def render(self) -> str:
        """渲染开关"""
        state = "[ON ]" if self.on else "[OFF]"
        if self.disabled:
            return f"{state} {self.label} (disabled)"
        return f"{state} {self.label}"
