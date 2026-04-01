"""
Hook Events - 事件类型定义

定义所有可用的钩子事件类型。
对应 Claude Code 源码: src/hooks/events.ts
参考: OpenClaw hooks 事件系统
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class EventType(Enum):
    """
    事件类型枚举。
    对应 Claude Code 源码: src/hooks/EventType
    
    事件分为几类：
    - Gateway 生命周期: startup, shutdown
    - 命令: new, reset, quit, custom
    - 会话: start, end, resume
    - 压缩: compaction:before, compaction:after
    - 工具: tool:before, tool:after, tool:error
    """
    # Gateway 生命周期
    GATEWAY_STARTUP = "gateway:startup"       # Gateway 启动时
    GATEWAY_SHUTDOWN = "gateway:shutdown"     # Gateway 关闭时
    
    # 命令事件
    COMMAND_NEW = "command:new"               # 执行 /new 命令
    COMMAND_RESET = "command:reset"           # 执行 /reset 命令
    COMMAND_QUIT = "command:quit"            # 执行 /quit 命令
    COMMAND_CUSTOM = "command:custom"         # 自定义命令
    
    # 会话事件
    SESSION_START = "session:start"          # 会话开始
    SESSION_END = "session:end"              # 会话结束
    SESSION_RESUME = "session:resume"        # 恢复会话
    
    # 压缩事件
    COMPACTION_BEFORE = "compaction:before"   # 压缩前触发
    COMPACTION_AFTER = "compaction:after"     # 压缩后触发
    
    # 工具事件
    TOOL_BEFORE = "tool:before"              # 工具执行前
    TOOL_AFTER = "tool:after"                # 工具执行后
    TOOL_ERROR = "tool:error"                # 工具执行错误


@dataclass
class HookEvent:
    """
    钩子事件实例。
    对应 Claude Code 源码: src/hooks/HookEvent
    
    当事件触发时，会创建一个 HookEvent 实例传递给钩子处理器。
    
    Attributes:
        type: 事件类型
        timestamp: 事件发生时间戳
        data: 事件数据（不同事件类型有不同的数据）
        source: 事件来源（如 agent_id, session_id）
    """
    type: EventType
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None  # 如 agent_id, session_id

    @property
    def datetime(self) -> datetime:
        """返回可读的时间"""
        return datetime.fromtimestamp(self.timestamp)

    def get(self, key: str, default: Any = None) -> Any:
        """从事件数据中获取值"""
        return self.data.get(key, default)

    def __repr__(self) -> str:
        return f"<HookEvent type={self.type.value} at {self.datetime.strftime('%H:%M:%S')}>"


# =============================================================================
# 事件数据类 - 为常见事件提供类型安全的 data 结构
# =============================================================================

@dataclass
class CommandEventData:
    """
    命令事件数据。
    用于 command:new, command:reset, command:quit 事件。
    """
    command: str              # 命令名称（如 "new", "reset"）
    args: List[str] = field(default_factory=list)  # 命令参数
    session_id: Optional[str] = None  # 会话 ID


@dataclass
class SessionEventData:
    """
    会话事件数据。
    用于 session:start, session:end, session:resume 事件。
    """
    session_id: str
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    message_count: int = 0  # 消息数量
    duration_seconds: float = 0  # 持续时间


@dataclass
class CompactionEventData:
    """
    压缩事件数据。
    用于 compaction:before, compaction:after 事件。
    """
    original_tokens: int      # 压缩前 token 数
    compressed_tokens: int    # 压缩后 token 数
    freed_tokens: int         # 释放的 token 数
    strategy: str = "unknown"  # 压缩策略


@dataclass
class ToolEventData:
    """
    工具事件数据。
    用于 tool:before, tool:after, tool:error 事件。
    """
    tool_name: str            # 工具名称
    tool_input: Dict[str, Any] = field(default_factory=dict)  # 工具输入
    tool_result: Any = None   # 工具结果（tool:after 时有）
    error: Optional[str] = None  # 错误信息（tool:error 时有）


# =============================================================================
# 事件创建工具函数
# =============================================================================

def create_command_event(
    command: str,
    args: Optional[List[str]] = None,
    session_id: Optional[str] = None,
) -> HookEvent:
    """创建命令事件"""
    return HookEvent(
        type=_command_event_type(command),
        data=CommandEventData(
            command=command,
            args=args or [],
            session_id=session_id,
        ).__dict__,
        source=session_id,
    )


def create_session_event(
    event_type: EventType,
    session_id: str,
    **kwargs,
) -> HookEvent:
    """创建会话事件"""
    return HookEvent(
        type=event_type,
        data=SessionEventData(
            session_id=session_id,
            **kwargs,
        ).__dict__,
        source=session_id,
    )


def create_compaction_event(
    event_type: EventType,
    original_tokens: int,
    compressed_tokens: int,
    freed_tokens: int,
    strategy: str = "unknown",
) -> HookEvent:
    """创建压缩事件"""
    return HookEvent(
        type=event_type,
        data=CompactionEventData(
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            freed_tokens=freed_tokens,
            strategy=strategy,
        ).__dict__,
    )


def create_tool_event(
    event_type: EventType,
    tool_name: str,
    tool_input: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> HookEvent:
    """创建工具事件"""
    return HookEvent(
        type=event_type,
        data=ToolEventData(
            tool_name=tool_name,
            tool_input=tool_input or {},
            **kwargs,
        ).__dict__,
    )


def _command_event_type(command: str) -> EventType:
    """根据命令名称返回事件类型"""
    mapping = {
        "new": EventType.COMMAND_NEW,
        "reset": EventType.COMMAND_RESET,
        "quit": EventType.COMMAND_QUIT,
    }
    return mapping.get(command.lower(), EventType.COMMAND_CUSTOM)


# =============================================================================
# 事件过滤器
# =============================================================================

class EventFilter:
    """
    事件过滤器。
    用于根据条件筛选要处理的事件。
    
    示例：
        filter = EventFilter(
            event_types=[EventType.COMMAND_NEW, EventType.COMMAND_RESET],
            session_ids=["session_123"],  # 可选：限定会话
        )
        
        if filter.matches(event):
            await hook.handle(event)
    """

    def __init__(
        self,
        event_types: Optional[List[EventType]] = None,
        session_ids: Optional[List[str]] = None,
        agents: Optional[List[str]] = None,
        custom_predicate: Optional[callable] = None,
    ) -> None:
        """
        初始化事件过滤器。
        
        Args:
            event_types: 要监听的事件类型列表（None 表示全部）
            session_ids: 要监听的会话 ID 列表（None 表示全部）
            agents: 要监听的 agent ID 列表（None 表示全部）
            custom_predicate: 自定义过滤函数 (HookEvent -> bool)
        """
        self.event_types = set(event_types) if event_types else None
        self.session_ids = set(session_ids) if session_ids else None
        self.agents = set(agents) if agents else None
        self.custom_predicate = custom_predicate

    def matches(self, event: HookEvent) -> bool:
        """
        检查事件是否匹配过滤条件。
        
        Args:
            event: 要检查的事件
            
        Returns:
            True 如果事件匹配所有条件
        """
        # 检查事件类型
        if self.event_types and event.type not in self.event_types:
            return False
        
        # 检查会话 ID
        if self.session_ids and event.source not in self.session_ids:
            return False
        
        # 检查 agent ID
        if self.agents:
            agent_id = event.get("agent_id")
            if agent_id not in self.agents:
                return False
        
        # 执行自定义过滤
        if self.custom_predicate and not self.custom_predicate(event):
            return False
        
        return True
