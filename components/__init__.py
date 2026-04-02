"""
Components Module - Ink UI Components

Claude Code 的 Ink/React 风格 UI 组件库。
对应 Claude Code 源码: src/components/*.tsx

包含：
- 基础组件（Text, Box, Spinner 等）
- 布局组件（Stack, Grid, Sidebar 等）
- 表单组件（Button, Input, Select 等）
- 展示组件（Table, List, Card 等）
- 反馈组件（Toast, Modal, Progress 等）
"""

from __future__ import annotations

from components.base import (
    Component,
    BaseText,
    BaseBox,
    BaseSpinner,
)
from components.primitives import (
    Text,
    Box,
    Spinner,
    Divider,
    Badge,
    Tag,
)
from components.layout import (
    Stack,
    HStack,
    VStack,
    Grid,
    Sidebar,
    SplitView,
)
from components.form import (
    Button,
    Input,
    Select,
    Checkbox,
    Radio,
    Switch,
)
from components.display import (
    Table,
    List,
    ListItem,
    Card,
    CardHeader,
    CardBody,
)
from components.feedback import (
    Toast,
    Modal,
    Alert,
    Progress,
    Skeleton,
)

__all__ = [
    # Base
    "Component",
    "BaseText",
    "BaseBox",
    "BaseSpinner",
    # Primitives
    "Text",
    "Box",
    "Spinner",
    "Divider",
    "Badge",
    "Tag",
    # Layout
    "Stack",
    "HStack",
    "VStack",
    "Grid",
    "Sidebar",
    "SplitView",
    # Form
    "Button",
    "Input",
    "Select",
    "Checkbox",
    "Radio",
    "Switch",
    # Display
    "Table",
    "List",
    "ListItem",
    "Card",
    "CardHeader",
    "CardBody",
    # Feedback
    "Toast",
    "Modal",
    "Alert",
    "Progress",
    "Skeleton",
]
