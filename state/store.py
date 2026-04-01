"""
State - 状态管理模块

提供类似 Zustand 的全局状态管理。
对应 Claude Code 源码: src/state/*.ts

核心概念：
1. Store - 状态容器
2. Selector - 状态选择器
3. Subscription - 状态订阅
4. Middleware - 中间件（logger, persist 等）
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generic, List, Optional, Set, TypeVar, Union

T = TypeVar("T")
U = TypeVar("U")

logger = logging.getLogger(__name__)


# =============================================================================
# Selector
# =============================================================================

class Selector(Generic[T]):
    """
    状态选择器。
    
    用于从 Store 中选择和派生状态。
    类似于 Zustand 的 selector 概念。
    
    示例：
        # 选择整个状态
        select_all = Selector(lambda state: state)
        
        # 选择特定字段
        select_user = Selector(lambda state: state.get("user"))
        
        # 带默认值
        select_count = Selector(lambda state: state.get("count", 0))
    """

    def __init__(
        self,
        fn: Callable[[Any], T],
        default: Optional[T] = None,
        equality_fn: Optional[Callable[[T, T], bool]] = None,
    ) -> None:
        """
        初始化选择器。
        
        Args:
            fn: 选择函数
            default: 默认值
            equality_fn: 相等性判断函数（用于判断是否需要通知订阅者）
        """
        self.fn = fn
        self.default = default
        self.equality_fn = equality_fn or self._default_equality

    def __call__(self, state: Any) -> T:
        """执行选择"""
        try:
            result = self.fn(state)
            return result if result is not None else self.default
        except Exception:
            return self.default

    @staticmethod
    def _default_equality(a: Any, b: Any) -> bool:
        """默认相等性判断"""
        return a == b


def create_selector(
    fn: Callable[[Any], T],
    default: Optional[T] = None,
) -> Selector[T]:
    """
    创建选择器的便捷函数。
    
    示例：
        selector = create_selector(lambda s: s.get("count"))
    """
    return Selector(fn, default)


# =============================================================================
# Subscription
# =============================================================================

class Subscription:
    """
    状态订阅。
    
    跟踪一个订阅者的信息。
    """

    def __init__(
        self,
        callback: Callable[[Any], None],
        selector: Optional[Selector[Any]] = None,
        unsubscribe_fn: Optional[Callable[[], None]] = None,
    ) -> None:
        self.callback = callback
        self.selector = selector
        self.unsubscribe_fn = unsubscribe_fn
        self._active = True

    def unsubscribe(self) -> None:
        """取消订阅"""
        self._active = False
        if self.unsubscribe_fn:
            self.unsubscribe_fn()

    @property
    def is_active(self) -> bool:
        return self._active


# =============================================================================
# Middleware
# =============================================================================

class Middleware(ABC):
    """
    中间件基类。
    
    中间件可以拦截 get、set、subscribe 等操作。
    用于日志持久化、调试等功能。
    
    示例：
        class LoggerMiddleware(Middleware):
            async def on_set(self, key, value, next_fn):
                logger.info(f"Setting {key} = {value}")
                return await next_fn()
    """

    @abstractmethod
    async def on_get(
        self,
        key: str,
        next_fn: Callable[[], Any],
    ) -> Any:
        """get 操作拦截"""
        raise NotImplementedError

    @abstractmethod
    async def on_set(
        self,
        key: str,
        value: Any,
        next_fn: Callable[[], None],
    ) -> None:
        """set 操作拦截"""
        raise NotImplementedError

    @abstractmethod
    async def on_subscribe(
        self,
        key: str,
        callback: Callable[[Any], None],
        next_fn: Callable[[], None],
    ) -> None:
        """subscribe 操作拦截"""
        raise NotImplementedError


class LoggerMiddleware(Middleware):
    """
    日志中间件。
    
    记录所有状态变更。
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger or logging.getLogger("state")

    async def on_get(self, key: str, next_fn: Callable[[], Any]) -> Any:
        return next_fn()

    async def on_set(
        self,
        key: str,
        value: Any,
        next_fn: Callable[[], None],
    ) -> None:
        self.logger.debug(f"State[{key}] = {value!r}")
        await next_fn()

    async def on_subscribe(
        self,
        key: str,
        callback: Callable[[Any], None],
        next_fn: Callable[[], None],
    ) -> None:
        self.logger.debug(f"Subscribed to State[{key}]")
        await next_fn()


class PersistMiddleware(Middleware):
    """
    持久化中间件。
    
    将状态保存到文件或存储后端。
    """

    def __init__(
        self,
        storage_path: str,
        interval_seconds: float = 30,
        debounce: bool = True,
    ) -> None:
        import json
        self.storage_path = storage_path
        self.interval = interval_seconds
        self.debounce = debounce
        self._pending = False
        self._save_task: Optional[asyncio.Task] = None

    async def on_get(self, key: str, next_fn: Callable[[], Any]) -> Any:
        return next_fn()

    async def on_set(
        self,
        key: str,
        value: Any,
        next_fn: Callable[[], None],
    ) -> None:
        await next_fn()
        
        if self.debounce and not self._pending:
            self._pending = True
            self._save_task = asyncio.create_task(self._delayed_save())

    async def on_subscribe(
        self,
        key: str,
        callback: Callable[[Any], None],
        next_fn: Callable[[], None],
    ) -> None:
        await next_fn()

    async def _delayed_save(self) -> None:
        await asyncio.sleep(self.interval)
        await self.save()
        self._pending = False

    async def save(self) -> None:
        """保存状态到文件"""
        # 触发时机由 Store 调用
        pass


# =============================================================================
# Store
# =============================================================================

class Store:
    """
    状态存储。
    
    对应 Claude Code 源码: src/state/store.ts (Zustand-like)
    
    提供：
    - 状态存取（get/set）
    - 订阅机制（subscribe）
    - 选择器（selector）
    - 中间件支持
    
    示例：
        store = Store(initial_state={"count": 0, "name": "test"})
        
        # 读取状态
        count = store.get("count")
        
        # 更新状态
        store.set("count", count + 1)
        
        # 订阅变更
        unsubscribe = store.subscribe(
            lambda state: state["count"],
            lambda count: print(f"Count changed: {count}")
        )
        
        # 取消订阅
        unsubscribe()
    """

    def __init__(
        self,
        initial_state: Optional[Dict[str, Any]] = None,
        middleware: Optional[List[Middleware]] = None,
        name: str = "store",
    ) -> None:
        """
        初始化 Store。
        
        Args:
            initial_state: 初始状态字典
            middleware: 中间件列表
            name: Store 名称（用于调试）
        """
        self._state: Dict[str, Any] = initial_state or {}
        self._middleware = middleware or []
        self._subscriptions: Dict[str, List[Subscription]] = {}  # key -> [Subscription]
        self._global_subscriptions: List[Subscription] = []  # 监听所有变更
        self._name = name
        self._lock = asyncio.Lock()

    # -------------------------------------------------------------------------
    # State Access
    # -------------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取状态值。
        
        Args:
            key: 状态键
            default: 默认值
            
        Returns:
            状态值
        """
        async def next_fn():
            return self._state.get(key, default)
        
        # 执行中间件链
        fn = next_fn
        for m in reversed(self._middleware):
            middleware = m
            async def wrapped(key=key, fn=fn, m=middleware):
                return await m.on_get(key, fn)
            fn = wrapped
        
        # 同步执行（用于兼容非异步调用）
        if asyncio.get_event_loop().is_running():
            # 在异步上下文中
            return asyncio.create_task(fn())
        else:
            return fn()

    def get_sync(self, key: str, default: Any = None) -> Any:
        """同步版本的 get（推荐在同步上下文中使用）"""
        return self._state.get(key, default)

    def get_state(self) -> Dict[str, Any]:
        """
        获取完整状态副本。
        
        Returns:
            状态字典的浅拷贝
        """
        return dict(self._state)

    # -------------------------------------------------------------------------
    # State Mutation
    # -------------------------------------------------------------------------

    async def set(self, key: str, value: Any) -> None:
        """
        设置状态值。
        
        Args:
            key: 状态键
            value: 新值
        """
        async def next_fn():
            self._state[key] = value
            await self._notify(key, value)

        # 执行中间件链
        fn = next_fn
        for m in reversed(self._middleware):
            middleware = m
            async def wrapped(key=key, value=value, fn=fn, m=middleware):
                return await m.on_set(key, value, fn)
            fn = wrapped
        
        await fn()

    def set_sync(self, key: str, value: Any) -> None:
        """
        同步版本 set（立即更新，不经过中间件）。
        
        推荐在初始化或批量更新时使用。
        """
        self._state[key] = value
        # 注意：同步版本不触发订阅通知
        # 如需通知，使用 await self.set()

    def update(self, updates: Dict[str, Any]) -> None:
        """
        批量更新状态。
        
        Args:
            updates: 要更新的键值对
        """
        for key, value in updates.items():
            self._state[key] = value
        
        # 通知所有变更
        for key, value in updates.items():
            asyncio.create_task(self._notify(key, value))

    # -------------------------------------------------------------------------
    # Subscription
    # -------------------------------------------------------------------------

    def subscribe(
        self,
        selector: Union[str, Selector[Any], Callable[[Dict[str, Any]], Any]],
        callback: Callable[[Any], None],
    ) -> Callable[[], None]:
        """
        订阅状态变更。
        
        Args:
            selector: 选择器（字符串键、Selector 对象或函数）
            callback: 状态变更时的回调
            
        Returns:
            取消订阅的函数
        """
        # 转换 selector
        if isinstance(selector, str):
            key = selector
            sel = Selector(lambda state: state.get(key))
        elif isinstance(selector, Selector):
            key = "__selector__"
            sel = selector
        else:
            key = "__selector__"
            sel = Selector(selector)

        # 创建订阅
        subscription = Subscription(
            callback=callback,
            selector=sel,
            unsubscribe_fn=None,
        )

        if key == "__selector__":
            # 全局订阅（通过 selector）
            self._global_subscriptions.append(subscription)
        else:
            # 键级别订阅
            if key not in self._subscriptions:
                self._subscriptions[key] = []
            self._subscriptions[key].append(subscription)

        # 返回取消订阅函数
        def unsubscribe():
            if key == "__selector__":
                if subscription in self._global_subscriptions:
                    self._global_subscriptions.remove(subscription)
            else:
                if key in self._subscriptions:
                    if subscription in self._subscriptions[key]:
                        self._subscriptions[key].remove(subscription)

        subscription.unsubscribe_fn = unsubscribe
        return unsubscribe

    def unsubscribe(self, key: str, callback: Callable[[Any], None]) -> None:
        """
        取消订阅。
        
        Args:
            key: 状态键
            callback: 之前订阅的回调
        """
        if key in self._subscriptions:
            subs = self._subscriptions[key]
            for sub in subs:
                if sub.callback == callback:
                    sub.unsubscribe()

    def _notify(self, key: str, value: Any) -> None:
        """
        通知订阅者。
        
        Args:
            key: 变更的键
            value: 新值
        """
        # 通知键级别订阅
        if key in self._subscriptions:
            for sub in self._subscriptions[key]:
                if sub.is_active:
                    try:
                        sub.callback(value)
                    except Exception as e:
                        logger.error(f"Subscription callback error: {e}")

        # 通知全局订阅
        current_state = self._state
        for sub in self._global_subscriptions:
            if sub.is_active:
                try:
                    selected = sub.selector(current_state)
                    sub.callback(selected)
                except Exception as e:
                    logger.error(f"Global subscription callback error: {e}")

    # -------------------------------------------------------------------------
    # Middleware
    # -------------------------------------------------------------------------

    def add_middleware(self, middleware: Middleware) -> None:
        """
        添加中间件。
        
        Args:
            middleware: 中间件实例
        """
        self._middleware.append(middleware)

    def remove_middleware(self, middleware: Middleware) -> None:
        """
        移除中间件。
        
        Args:
            middleware: 中间件实例
        """
        if middleware in self._middleware:
            self._middleware.remove(middleware)

    # -------------------------------------------------------------------------
    # Snapshot / Persistence
    # -------------------------------------------------------------------------

    def get_snapshot(self) -> Dict[str, Any]:
        """
        获取状态快照（用于持久化）。
        
        Returns:
            状态字典
        """
        return dict(self._state)

    def load_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """
        加载状态快照。
        
        Args:
            snapshot: 之前保存的状态
        """
        self._state = dict(snapshot)

    # -------------------------------------------------------------------------
    # Debug
    # -------------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"<Store name={self._name} keys={list(self._state.keys())}>"
