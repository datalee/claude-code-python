"""
Hook Registry - 钩子注册表

管理所有钩子的注册、发现和执行。
对应 Claude Code 源码: src/hooks/HookRegistry.ts
参考: OpenClaw hooks 系统
"""

from __future__ import annotations

import asyncio
import importlib
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

from hook.base import Hook, HookConfig, HookResult, HookStatus
from hook.events import EventType, HookEvent


logger = logging.getLogger(__name__)


class HookRegistry:
    """
    钩子注册表。
    对应 Claude Code 源码: src/hooks/HookRegistry
    参考: OpenClaw hooks 系统
    
    职责：
    1. 维护所有已注册钩子
    2. 根据事件类型分发事件
    3. 管理钩子的启用/禁用
    4. 钩子生命周期管理
    
    设计：
    - 全局单例模式
    - 线程安全（asyncio）
    - 支持内置钩子和外部钩子
    
    示例：
        registry = HookRegistry()
        
        # 注册钩子
        registry.register(SessionMemoryHook())
        registry.register(CommandLoggerHook())
        
        # 分发事件
        event = create_command_event("new", session_id="sess_123")
        await registry.emit(event)
    """

    def __init__(self) -> None:
        """初始化注册表"""
        self._hooks: Dict[str, Hook] = {}  # name -> Hook
        self._event_subscriptions: Dict[EventType, List[str]] = {}  # EventType -> [hook_names]
        self._global_filters: List[Callable[[HookEvent], bool]] = []
        self._enabled: bool = True

    # -------------------------------------------------------------------------
    # 注册与注销
    # -------------------------------------------------------------------------

    def register(self, hook: Hook) -> None:
        """
        注册一个钩子。
        
        Args:
            hook: 钩子实例
            
        Raises:
            ValueError: 如果钩子名称已存在
        """
        if hook.name in self._hooks:
            raise ValueError(f"Hook '{hook.name}' is already registered")
        
        # 验证配置
        valid, error = hook.validate_config()
        if not valid:
            logger.warning(f"Hook '{hook.name}' has invalid config: {error}")
        
        # 注册钩子
        self._hooks[hook.name] = hook
        
        # 建立事件订阅
        for event_type in hook.get_events():
            if event_type not in self._event_subscriptions:
                self._event_subscriptions[event_type] = []
            self._event_subscriptions[event_type].append(hook.name)
        
        logger.info(f"Registered hook: {hook.name}")

    def unregister(self, name: str) -> Optional[Hook]:
        """
        注销一个钩子。
        
        Args:
            name: 钩子名称
            
        Returns:
            被注销的钩子实例
        """
        hook = self._hooks.pop(name, None)
        if hook is None:
            return None
        
        # 移除事件订阅
        for event_type, hook_names in self._event_subscriptions.items():
            if name in hook_names:
                hook_names.remove(name)
        
        logger.info(f"Unregistered hook: {name}")
        return hook

    def get(self, name: str) -> Optional[Hook]:
        """
        获取指定名称的钩子。
        
        Args:
            name: 钩子名称
            
        Returns:
            钩子实例或 None
        """
        return self._hooks.get(name)

    def list_hooks(self, enabled_only: bool = False) -> List[Hook]:
        """
        列出所有钩子。
        
        Args:
            enabled_only: 是否只返回已启用的钩子
            
        Returns:
            钩子列表
        """
        hooks = list(self._hooks.values())
        if enabled_only:
            hooks = [h for h in hooks if h.is_enabled]
        return hooks

    # -------------------------------------------------------------------------
    # 事件分发
    # -------------------------------------------------------------------------

    async def emit(self, event: HookEvent) -> List[HookResult]:
        """
        分发事件给所有订阅的钩子。
        
        Args:
            event: 事件对象
            
        Returns:
            所有钩子的执行结果列表
        """
        if not self._enabled:
            return []
        
        # 收集需要执行的钩子
        hook_names = self._event_subscriptions.get(event.type, [])
        hooks = [self._hooks[name] for name in hook_names if name in self._hooks]
        
        if not hooks:
            return []
        
        # 过滤
        hooks = [h for h in hooks if h.matches_event(event)]
        
        # 应用全局过滤器
        for filter_fn in self._global_filters:
            if not filter_fn(event):
                return []
        
        # 并行执行所有匹配的钩子
        tasks = [h.execute(event) for h in hooks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        processed_results: List[HookResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(HookResult.err(str(result)))
            else:
                processed_results.append(result)
        
        return processed_results

    async def emit_one(self, event: HookEvent) -> Optional[HookResult]:
        """
        分发事件给单个钩子（第一个匹配的）。
        
        适用于只需要一个钩子处理的场景。
        
        Args:
            event: 事件对象
            
        Returns:
            第一个执行的钩子结果，或 None
        """
        hook_names = self._event_subscriptions.get(event.type, [])
        
        for name in hook_names:
            hook = self._hooks.get(name)
            if hook and hook.matches_event(event):
                return await hook.execute(event)
        
        return None

    # -------------------------------------------------------------------------
    # 钩子控制
    # -------------------------------------------------------------------------

    def enable(self, name: str) -> bool:
        """
        启用指定钩子。
        
        Args:
            name: 钩子名称
            
        Returns:
            是否成功
        """
        hook = self._hooks.get(name)
        if hook is None:
            return False
        
        hook.config.enabled = True
        logger.info(f"Enabled hook: {name}")
        return True

    def disable(self, name: str) -> bool:
        """
        禁用指定钩子。
        
        Args:
            name: 钩子名称
            
        Returns:
            是否成功
        """
        hook = self._hooks.get(name)
        if hook is None:
            return False
        
        hook.config.enabled = False
        logger.info(f"Disabled hook: {name}")
        return True

    def enable_all(self) -> None:
        """启用所有钩子"""
        for hook in self._hooks.values():
            hook.config.enabled = True
        logger.info("Enabled all hooks")

    def disable_all(self) -> None:
        """禁用所有钩子"""
        for hook in self._hooks.values():
            hook.config.enabled = False
        logger.info("Disabled all hooks")

    # -------------------------------------------------------------------------
    # 全局过滤器
    # -------------------------------------------------------------------------

    def add_global_filter(self, filter_fn: Callable[[HookEvent], bool]) -> None:
        """
        添加全局事件过滤器。
        
        所有事件都会先经过此过滤器，只有返回 True 的事件才会被分发。
        
        Args:
            filter_fn: 过滤函数
        """
        self._global_filters.append(filter_fn)

    def clear_global_filters(self) -> None:
        """清除所有全局过滤器"""
        self._global_filters.clear()

    # -------------------------------------------------------------------------
    # 注册表控制
    # -------------------------------------------------------------------------

    def enable_registry(self) -> None:
        """启用注册表（允许事件分发）"""
        self._enabled = True

    def disable_registry(self) -> None:
        """禁用注册表（暂停事件分发）"""
        self._enabled = False

    @property
    def is_enabled(self) -> bool:
        """注册表是否启用"""
        return self._enabled

    # -------------------------------------------------------------------------
    # 发现与加载
    # -------------------------------------------------------------------------

    def discover_builtin_hooks(self) -> List[Hook]:
        """
        发现并返回所有内置钩子。
        
        Returns:
            内置钩子实例列表
        """
        # 延迟导入避免循环依赖
        from hook.builtin import (
            SessionMemoryHook,
            CommandLoggerHook,
            BootMdHook,
        )
        
        return [
            SessionMemoryHook(),
            CommandLoggerHook(),
            BootMdHook(),
        ]

    async def load_hooks_from_directory(self, directory: Path) -> int:
        """
        从目录加载钩子。
        
        扫描目录下的 Python 文件，实例化所有 Hook 子类。
        
        Args:
            directory: 包含钩子的目录
            
        Returns:
            加载的钩子数量
        """
        loaded = 0
        
        for file_path in directory.glob("*.py"):
            if file_path.name.startswith("_"):
                continue
            
            try:
                # 动态导入模块
                module_name = f"hook.builtin.{file_path.stem}"
                module = importlib.import_module(module_name)
                
                # 查找 Hook 子类
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, Hook)
                        and attr is not Hook
                    ):
                        hook = attr()
                        self.register(hook)
                        loaded += 1
                        
            except Exception as e:
                logger.warning(f"Failed to load hooks from {file_path}: {e}")
        
        return loaded

    # -------------------------------------------------------------------------
    # 状态查询
    # -------------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """
        获取注册表状态。
        
        Returns:
            状态信息字典
        """
        hooks = self.list_hooks()
        enabled = [h for h in hooks if h.is_enabled]
        
        # 按事件类型分组
        by_event: Dict[str, int] = {}
        for event_type, hook_names in self._event_subscriptions.items():
            by_event[event_type.value] = len(hook_names)
        
        return {
            "total_hooks": len(hooks),
            "enabled_hooks": len(enabled),
            "disabled_hooks": len(hooks) - len(enabled),
            "registry_enabled": self._enabled,
            "hooks_by_event": by_event,
            "hooks": [
                {
                    "name": h.name,
                    "status": h.status.value,
                    "events": [e.value for e in h.get_events()],
                }
                for h in hooks
            ],
        }


# =============================================================================
# 全局注册表实例
# =============================================================================

_global_registry: Optional[HookRegistry] = None


def get_hook_registry() -> HookRegistry:
    """
    获取全局钩子注册表实例。
    
    Returns:
        全局注册表（单例）
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = HookRegistry()
    return _global_registry
