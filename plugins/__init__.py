"""
Plugins Module - 插件系统

可插拔的扩展系统，允许动态加载第三方插件。
对应 Claude Code 源码: src/plugins/*.ts
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

# ============================================================================
# 插件接口
# ============================================================================

class Plugin:
    """
    插件基类。
    
    所有插件必须继承此类。
    
    示例：
        class MyPlugin(Plugin):
            name = "my_plugin"
            version = "1.0.0"
            description = "My custom plugin"
            
            def on_load(self) -> None:
                # 插件加载时调用
                pass
            
            def on_unload(self) -> None:
                # 插件卸载时调用
                pass
    """
    
    name: str = ""
    version: str = ""
    description: str = ""
    author: str = ""
    dependencies: List[str] = []
    
    def on_load(self) -> None:
        """插件加载时调用"""
        pass
    
    def on_unload(self) -> None:
        """插件卸载时调用"""
        pass
    
    def on_startup(self) -> None:
        """应用启动时调用"""
        pass
    
    def on_shutdown(self) -> None:
        """应用关闭时调用"""
        pass


# ============================================================================
# 插件元数据
# ============================================================================

@dataclass
class PluginMetadata:
    """插件元数据"""
    name: str
    version: str
    description: str = ""
    author: str = ""
    plugin_class: Optional[Type[Plugin]] = None
    file_path: Optional[str] = None
    enabled: bool = True
    loaded: bool = False
    error: Optional[str] = None


# ============================================================================
# PluginRegistry
# ============================================================================

class PluginRegistry:
    """
    插件注册表。
    
    管理所有插件的注册、发现、加载和卸载。
    
    示例：
        registry = PluginRegistry()
        registry.discover_plugins()
        registry.load_plugin("my_plugin")
        
        # 调用所有已加载插件的 hook
        for plugin in registry.get_active_plugins():
            plugin.on_startup()
    """
    
    def __init__(self) -> None:
        self.plugins: Dict[str, PluginMetadata] = {}
        self._hooks: Dict[str, List[Callable]] = {}
    
    # =========================================================================
    # 注册 & 发现
    # =========================================================================
    
    def register(self, plugin_class: Type[Plugin], file_path: Optional[str] = None) -> None:
        """
        注册一个插件类。
        
        Args:
            plugin_class: Plugin 子类
            file_path: 插件文件路径
        """
        name = getattr(plugin_class, "name", "")
        if not name:
            raise ValueError("Plugin must have a 'name' attribute")
        
        metadata = PluginMetadata(
            name=name,
            version=getattr(plugin_class, "version", "1.0.0"),
            description=getattr(plugin_class, "description", ""),
            author=getattr(plugin_class, "author", ""),
            plugin_class=plugin_class,
            file_path=file_path,
        )
        
        self.plugins[name] = metadata
    
    def discover_plugins(self, plugin_dir: Optional[Path] = None) -> List[str]:
        """
        发现插件目录中的所有插件。
        
        Args:
            plugin_dir: 插件目录，默认 ~/.claude/plugins/
            
        Returns:
            发现的插件名称列表
        """
        if plugin_dir is None:
            plugin_dir = Path.home() / ".claude" / "plugins"
        
        plugin_dir.mkdir(parents=True, exist_ok=True)
        
        discovered = []
        
        for file_path in plugin_dir.iterdir():
            if file_path.suffix == ".py" and not file_path.name.startswith("_"):
                try:
                    spec = importlib.util.spec_from_file_location(
                        f"plugin_{file_path.stem}",
                        file_path
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[f"plugin_{file_path.stem}"] = module
                        spec.loader.exec_module(module)
                        
                        # 查找 Plugin 子类
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            if isinstance(attr, type) and issubclass(attr, Plugin) and attr is not Plugin:
                                self.register(attr, str(file_path))
                                discovered.append(attr.name)
                
                except Exception as e:
                    # 记录错误但不中断
                    pass
        
        return discovered
    
    # =========================================================================
    # 加载 & 卸载
    # =========================================================================
    
    def load_plugin(self, name: str) -> bool:
        """
        加载指定插件。
        
        Args:
            name: 插件名称
            
        Returns:
            是否加载成功
        """
        if name not in self.plugins:
            return False
        
        metadata = self.plugins[name]
        
        if metadata.loaded:
            return True
        
        if not metadata.enabled:
            return False
        
        try:
            # 实例化插件
            plugin_instance = metadata.plugin_class()
            
            # 替换为实例
            metadata.plugin_class = None  # type: ignore
            self.plugins[name] = metadata
            
            # 调用 on_load
            plugin_instance.on_load()
            
            metadata.loaded = True
            metadata.error = None
            
            return True
        
        except Exception as e:
            metadata.error = str(e)
            return False
    
    def unload_plugin(self, name: str) -> bool:
        """
        卸载指定插件。
        
        Args:
            name: 插件名称
            
        Returns:
            是否卸载成功
        """
        if name not in self.plugins:
            return False
        
        metadata = self.plugins[name]
        
        if not metadata.loaded:
            return True
        
        try:
            # 获取实例并调用 on_unload
            # 需要重新实例化来调用 on_unload
            if metadata.plugin_class is None:
                plugin_instance = metadata.plugin_class()
                plugin_instance.on_unload()
            
            metadata.loaded = False
            return True
        
        except Exception as e:
            metadata.error = str(e)
            return False
    
    def enable_plugin(self, name: str) -> bool:
        """启用插件"""
        if name not in self.plugins:
            return False
        self.plugins[name].enabled = True
        return True
    
    def disable_plugin(self, name: str) -> bool:
        """禁用插件"""
        if name not in self.plugins:
            return False
        self.plugins[name].enabled = False
        return True
    
    # =========================================================================
    # 查询
    # =========================================================================
    
    def get_plugin(self, name: str) -> Optional[PluginMetadata]:
        """获取插件元数据"""
        return self.plugins.get(name)
    
    def get_all_plugins(self) -> List[PluginMetadata]:
        """获取所有插件"""
        return list(self.plugins.values())
    
    def get_active_plugins(self) -> List[Plugin]:
        """获取所有已加载的插件实例"""
        active = []
        for metadata in self.plugins.values():
            if metadata.loaded and metadata.plugin_class is not None:
                try:
                    # 如果是类而非实例，重新实例化
                    if isinstance(metadata.plugin_class, type):
                        active.append(metadata.plugin_class())
                    elif isinstance(metadata.plugin_class, Plugin):
                        active.append(metadata.plugin_class)
                except Exception:
                    pass
        return active
    
    def get_enabled_plugins(self) -> List[PluginMetadata]:
        """获取所有已启用的插件"""
        return [p for p in self.plugins.values() if p.enabled]
    
    # =========================================================================
    # Hook 系统
    # =========================================================================
    
    def register_hook(self, event: str, callback: Callable) -> None:
        """
        注册一个 hook 回调。
        
        Args:
            event: 事件名称
            callback: 回调函数
        """
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(callback)
    
    def unregister_hook(self, event: str, callback: Callable) -> None:
        """取消注册 hook"""
        if event in self._hooks:
            self._hooks[event] = [cb for cb in self._hooks[event] if cb != callback]
    
    async def emit_hook(self, event: str, *args: Any, **kwargs: Any) -> List[Any]:
        """
        触发一个 hook。
        
        Args:
            event: 事件名称
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            所有回调的返回值列表
        """
        results = []
        if event in self._hooks:
            for callback in self._hooks[event]:
                try:
                    result = callback(*args, **kwargs)
                    if hasattr(result, "__await__"):
                        result = await result
                    results.append(result)
                except Exception:
                    pass
        return results
    
    # =========================================================================
    # 管理
    # =========================================================================
    
    def list_plugins(self) -> List[Dict[str, Any]]:
        """列出所有插件（格式化）"""
        return [
            {
                "name": p.name,
                "version": p.version,
                "description": p.description,
                "enabled": p.enabled,
                "loaded": p.loaded,
                "error": p.error,
            }
            for p in self.plugins.values()
        ]
    
    def clear(self) -> None:
        """清除所有已注册的插件"""
        self.plugins.clear()
        self._hooks.clear()


# ============================================================================
# 插件管理器（REPL 集成）
# ============================================================================

class PluginManager:
    """
    插件管理器。
    
    提供 REPL 命令来管理插件。
    """
    
    def __init__(self, registry: Optional[PluginRegistry] = None) -> None:
        self.registry = registry or PluginRegistry()
    
    async def install_plugin(self, name: str, source: str) -> bool:
        """
        安装插件（从源路径或 pip 包）。
        
        Args:
            name: 插件名称
            source: 源路径或包名
            
        Returns:
            是否安装成功
        """
        # TODO: 实现安装逻辑
        return False
    
    async def uninstall_plugin(self, name: str) -> bool:
        """
        卸载插件。
        
        Args:
            name: 插件名称
            
        Returns:
            是否卸载成功
        """
        # TODO: 实现卸载逻辑
        return False


# ============================================================================
# 全局实例
# ============================================================================

_registry: Optional[PluginRegistry] = None


def get_plugin_registry() -> PluginRegistry:
    """获取全局插件注册表"""
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
    return _registry


# ============================================================================
# 内置插件示例
# ============================================================================

class HelloWorldPlugin(Plugin):
    """示例插件：Hello World"""
    
    name = "hello_world"
    version = "1.0.0"
    description = "Example plugin that prints hello"
    author = "Claude Code"
    
    def on_load(self) -> None:
        print(f"[hello_world] Plugin loaded!")
    
    def on_startup(self) -> None:
        print("Hello from HelloWorldPlugin!")


__all__ = [
    "Plugin",
    "PluginMetadata",
    "PluginRegistry",
    "PluginManager",
    "get_plugin_registry",
    "HelloWorldPlugin",
]
