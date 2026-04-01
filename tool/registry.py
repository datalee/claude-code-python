"""
Tool Registry - Central registration and lookup for all available tools.

Corresponds to: src/Tool.ts ~ToolRegistry~ class (part of the Registry Pattern)

Design pattern: Registry Pattern (GoF)
- Provides a central registry of all tools
- Tools register themselves at import time via decorator or explicit registration
- Enables dynamic tool discovery and LLM tool definition generation

The registry is used by:
1. QueryEngine to get all available tools for the LLM
2. Permission system to check tool permissions
3. CLI to list available tools
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from tool.base import Tool, ToolResult


class ToolRegistry:
    """
    Central registry for all tools.
    
    Corresponds to: src/Tool.ts ~ToolRegistry~
    
    Implements the Registry Pattern:
    - Tools are registered by name
    - Lookup by name is O(1)
    - Supports listing all tools, filtering by capability
    
    Singleton: Use get_tool_registry() to get the global instance.
    
    Example:
        registry = get_tool_registry()
        
        # Register a tool
        registry.register(MyCustomTool())
        
        # Lookup a tool
        tool = registry.get("bash")
        
        # Get all tools for LLM
        llm_tools = registry.get_llm_tools()
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._tools: Dict[str, Tool] = {}
        self._lock = False  # Prevent further registration after lock

    def register(self, tool: Tool) -> None:
        """
        Register a tool instance.
        
        Args:
            tool: An instance of a Tool subclass
            
        Raises:
            ValueError: If a tool with the same name is already registered
            RuntimeError: If the registry is locked
        """
        if self._lock:
            raise RuntimeError("Tool registry is locked; cannot register new tools")

        if not tool.name:
            raise ValueError("Tool must have a non-empty name")

        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")

        self._tools[tool.name] = tool

    def register_class(self, tool_class: Type[Tool]) -> None:
        """
        Register a tool by its class (instantiates with default constructor).
        
        Args:
            tool_class: A Tool subclass (not an instance)
        """
        self.register(tool_class())

    def get(self, name: str) -> Optional[Tool]:
        """
        Get a tool by name.
        
        Args:
            name: The tool's unique identifier
            
        Returns:
            The Tool instance, or None if not found
        """
        return self._tools.get(name)

    def get_or_raise(self, name: str) -> Tool:
        """
        Get a tool by name, raising if not found.
        
        Args:
            name: The tool's unique identifier
            
        Returns:
            The Tool instance
            
        Raises:
            KeyError: If no tool with that name exists
        """
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Tool '{name}' not found in registry")
        return tool

    def unregister(self, name: str) -> bool:
        """
        Remove a tool from the registry.
        
        Args:
            name: The tool's unique identifier
            
        Returns:
            True if the tool was removed, False if it wasn't registered
        """
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def list_tools(self) -> List[str]:
        """
        List all registered tool names.
        
        Returns:
            List of tool names
        """
        return list(self._tools.keys())

    def get_all_tools(self) -> List[Tool]:
        """
        Get all registered tool instances.
        
        Returns:
            List of all Tool instances
        """
        return list(self._tools.values())

    def get_llm_tools(self) -> List[Dict[str, Any]]:
        """
        Get tool definitions formatted for LLM tool-calling API.
        
        Corresponds to: The tool definitions sent to Anthropic/OpenAI API
        
        Returns:
            List of tool definition dicts with 'name', 'description', 'input_schema'
        """
        return [tool.get_metadata() for tool in self._tools.values()]

    def lock(self) -> None:
        """
        Lock the registry to prevent further tool registration.
        
        Call this after all tools are registered and before
        starting the agent loop.
        """
        self._lock = True

    @property
    def is_locked(self) -> bool:
        """Return True if the registry is locked."""
        return self._lock

    def __len__(self) -> int:
        return len(self._tools)

    def __repr__(self) -> str:
        return f"<ToolRegistry tools={self.list_tools()}>"


# ---------------------------------------------------------------------------
# Global registry instance
# ---------------------------------------------------------------------------

# The global registry instance. Initialize once, use everywhere.
_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """
    Get the global ToolRegistry instance.
    
    This is a singleton accessor - only one registry exists per process.
    
    Returns:
        The global ToolRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def register_tool(tool: Tool) -> None:
    """
    Convenience function to register a tool with the global registry.
    
    Example:
        @register_tool
        class MyTool(Tool):
            ...
    
    Or:
        register_tool(BashTool())
    """
    get_tool_registry().register(tool)


def create_registry() -> ToolRegistry:
    """
    Factory function to create a new registry.
    
    Note: Usually you want get_tool_registry() instead.
    This is mainly useful for testing or isolated environments.
    
    Returns:
        A new ToolRegistry instance
    """
    return ToolRegistry()
