"""
Hook Base - 钩子抽象基类

定义所有钩子的通用接口和配置。
对应 Claude Code 源码: src/hooks/Hook.ts
参考: OpenClaw hooks 系统
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from hook.events import EventType, HookEvent, EventFilter


class HookStatus(Enum):
    """
    钩子状态。
    """
    DISABLED = "disabled"     # 已禁用
    ENABLED = "enabled"       # 已启用
    READY = "ready"          # 就绪（满足条件）
    ERROR = "error"          # 执行错误


@dataclass
class HookConfig:
    """
    钩子配置。
    对应 Claude Code 源码: src/hooks/HookConfig
    
    Attributes:
        enabled: 是否启用
        async_execute: 是否异步执行（不阻塞主流程）
        timeout_ms: 超时时间（毫秒）
        retry_count: 失败重试次数
        conditions: 触发条件列表
    """
    enabled: bool = True
    async_execute: bool = True   # 默认异步执行，不阻塞
    timeout_ms: Optional[int] = None  # None 表示无超时
    retry_count: int = 0         # 0 表示不重试
    conditions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class HookResult:
    """
    钩子执行结果。
    对应 Claude Code 源码: src/hooks/HookResult
    
    Attributes:
        success: 是否执行成功
        output: 执行输出（任何可序列化内容）
        error: 错误信息
        duration_ms: 执行耗时（毫秒）
        timestamp: 执行时间戳
    """
    success: bool
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0
    timestamp: float = field(default_factory=time.time)

    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }

    @classmethod
    def ok(cls, output: Any = None, duration_ms: float = 0) -> HookResult:
        """创建成功结果"""
        return cls(success=True, output=output, duration_ms=duration_ms)

    @classmethod
    def err(cls, error: str, duration_ms: float = 0) -> HookResult:
        """创建错误结果"""
        return cls(success=False, error=error, duration_ms=duration_ms)


class Hook(ABC):
    """
    钩子抽象基类。
    对应 Claude Code 源码: src/hooks/Hook (基类)
    
    所有钩子必须继承此类并实现核心方法。
    
    钩子是事件驱动的自动化单元：
    1. 订阅特定事件类型
    2. 事件发生时自动执行
    3. 可选：返回结果或执行副作用
    
    设计原则：
    - 钩子应该是轻量级的，快速执行
    - 长时间任务应该异步执行
    - 失败不应该中断主流程（除非明确配置）
    
    示例：
        class SessionMemoryHook(Hook):
            name = "session-memory"
            description = "保存会话上下文到记忆"
            
            def get_events(self) -> List[EventType]:
                return [EventType.COMMAND_NEW, EventType.SESSION_END]
            
            async def handle(self, event: HookEvent) -> HookResult:
                # 保存会话上下文
                await self.save_session_context(event)
                return HookResult.ok()
    """

    # ------------------------------------------------------------------
    # 类属性（子类必须定义）
    # ------------------------------------------------------------------

    name: str = ""
    """钩子唯一名称，如 'session-memory'"""

    description: str = ""
    """人类可读的描述"""

    version: str = "1.0.0"
    """钩子版本"""

    # ------------------------------------------------------------------
    # 配置
    # ------------------------------------------------------------------

    config: HookConfig = field(default_factory=HookConfig)
    """钩子配置"""

    # ------------------------------------------------------------------
    # 抽象方法（子类必须实现）
    # ------------------------------------------------------------------

    @abstractmethod
    def get_events(self) -> List[EventType]:
        """
        返回此钩子订阅的事件类型列表。
        
        Returns:
            要监听的事件类型列表
        """
        raise NotImplementedError

    @abstractmethod
    async def handle(self, event: HookEvent) -> HookResult:
        """
        处理事件。
        
        当订阅的事件发生时，此方法会被调用。
        
        Args:
            event: 事件对象
            
        Returns:
            执行结果
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # 可选覆盖方法
    # ------------------------------------------------------------------

    def get_filter(self) -> Optional[EventFilter]:
        """
        返回事件过滤器。
        
        如果返回 None，则接受所有匹配事件类型的事件。
        如果返回 EventFilter，则只有满足条件的事件才会触发此钩子。
        
        Returns:
            事件过滤器或 None
        """
        return None

    async def on_enable(self) -> None:
        """
        钩子启用时的回调。
        
        可用于初始化资源、验证配置等。
        """
        pass

    async def on_disable(self) -> None:
        """
        钩子禁用时的回调。
        
        可用于清理资源、保存状态等。
        """
        pass

    def validate_config(self) -> tuple[bool, Optional[str]]:
        """
        验证钩子配置。
        
        Returns:
            (是否有效, 错误信息)
        """
        return True, None

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @property
    def status(self) -> HookStatus:
        """获取钩子状态"""
        if not self.config.enabled:
            return HookStatus.DISABLED
        
        valid, _ = self.validate_config()
        if not valid:
            return HookStatus.ERROR
        
        return HookStatus.READY

    @property
    def is_enabled(self) -> bool:
        """检查钩子是否启用"""
        return self.config.enabled and self.status == HookStatus.READY

    def matches_event(self, event: HookEvent) -> bool:
        """
        检查事件是否匹配此钩子。
        
        Args:
            event: 要检查的事件
            
        Returns:
            True 如果事件应该触发此钩子
        """
        # 检查事件类型
        if event.type not in self.get_events():
            return False
        
        # 检查过滤器
        filter_obj = self.get_filter()
        if filter_obj is not None:
            return filter_obj.matches(event)
        
        return True

    async def execute(self, event: HookEvent) -> HookResult:
        """
        执行钩子（带错误处理和重试）。
        
        Args:
            event: 事件对象
            
        Returns:
            执行结果
        """
        start_time = time.time()
        
        # 检查是否启用
        if not self.is_enabled:
            return HookResult.err(f"Hook {self.name} is not enabled")
        
        # 验证配置
        valid, error = self.validate_config()
        if not valid:
            return HookResult.err(f"Config validation failed: {error}")
        
        # 执行（带重试）
        last_error = None
        for attempt in range(self.config.retry_count + 1):
            try:
                result = await self._execute_with_timeout(event)
                result.duration_ms = (time.time() - start_time) * 1000
                return result
            except Exception as e:
                last_error = str(e)
                if attempt < self.config.retry_count:
                    # 重试前等待（指数退避）
                    import asyncio
                    await asyncio.sleep(2 ** attempt * 0.1)
        
        return HookResult.err(
            f"Hook failed after {self.config.retry_count + 1} attempts: {last_error}",
            duration_ms=(time.time() - start_time) * 1000,
        )

    async def _execute_with_timeout(self, event: HookEvent) -> HookResult:
        """带超时的执行"""
        import asyncio
        
        if self.config.timeout_ms is None:
            return await self.handle(event)
        
        timeout_seconds = self.config.timeout_ms / 1000
        
        try:
            # 使用 asyncio.wait_for 实现超时控制
            result = await asyncio.wait_for(
                self.handle(event),
                timeout=timeout_seconds
            )
            return result
        except asyncio.TimeoutError:
            return HookResult(
                success=False,
                message=f"Hook '{self.name}' execution timed out after {timeout_seconds}s",
                data={"timeout_ms": self.config.timeout_ms},
            )

    def __repr__(self) -> str:
        return f"<Hook name={self.name} status={self.status.value}>"
