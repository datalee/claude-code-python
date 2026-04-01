"""
Tool Base Classes and Permission Model

Corresponds to: src/Tool.ts (Tool base class + permission model)

Core concepts:
- Tool: Abstract base class for all tools with name, description, input_schema, permissions
- ToolResult: Standardized result type returned by tool execution
- Permission / PermissionScope / PermissionMode: Permission model for tool access control
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class PermissionMode(Enum):
    """
    Permission mode determines how a tool's execution is authorized.
    
    Corresponds to: src/Tool.ts ~PermissionMode~
    
    - ASK: Always ask user for permission before executing
    - AUTOMATIC: Execute without asking (for trusted operations like read-only tools)
    - NEVER: Never execute (disabled tool)
    """

    ASK = "ask"
    AUTOMATIC = "automatic"
    NEVER = "never"


class PermissionScope(Enum):
    """
    Scope of the permission - limits what resources a tool can access.
    
    Corresponds to: src/Tool.ts ~PermissionScope~
    
    - READ: Only read operations (read file, list directory, etc.)
    - WRITE: Write operations (create/modify files, run commands)
    - NETWORK: Network access (HTTP requests, etc.)
    - ENVIRONMENT: Environment variable access
    - ALL: Full access to all resources
    """

    READ = "read"
    WRITE = "write"
    NETWORK = "network"
    ENVIRONMENT = "environment"
    ALL = "all"


@dataclass
class Permission:
    """
    Permission configuration for a tool.
    
    Corresponds to: src/Tool.ts ~Permission~ interface
    
    Attributes:
        mode: How to authorize this tool (ask, automatic, never)
        scope: What resources this tool can access
        timeout_ms: Max execution time in milliseconds (None = no limit)
        allowed_paths: List of path prefixes this tool can access (None = all)
        denied_paths: List of path prefixes this tool cannot access
    """

    mode: PermissionMode = PermissionMode.ASK
    scope: PermissionScope = PermissionScope.ALL
    timeout_ms: Optional[int] = None
    allowed_paths: Optional[List[str]] = None
    denied_paths: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize permission to dict for LLM tool definitions."""
        return {
            "mode": self.mode.value,
            "scope": self.scope.value,
            "timeout_ms": self.timeout_ms,
            "allowed_paths": self.allowed_paths,
            "denied_paths": self.denied_paths,
        }


@dataclass
class ToolResult:
    """
    Standardized result returned by every tool execution.
    
    Corresponds to: src/Tool.ts ~ToolResult~ interface
    
    Attributes:
        success: Whether the tool executed successfully
        content: The output content (text, error message, etc.)
        error: Error message if success=False
        metadata: Additional metadata (execution time, files modified, etc.)
    """

    success: bool
    content: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for API responses."""
        return {
            "success": self.success,
            "content": self.content,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def ok(cls, content: str, **metadata: Any) -> ToolResult:
        """Create a successful result."""
        return cls(success=True, content=content, metadata=metadata)

    @classmethod
    def err(cls, error: str, **metadata: Any) -> ToolResult:
        """Create an error result."""
        return cls(success=False, error=error, metadata=metadata)


class Tool(ABC):
    """
    Abstract base class for all tools.
    
    Corresponds to: src/Tool.ts ~Tool~ abstract class
    
    All tools must implement:
    - name: Unique identifier for the tool
    - description: Human-readable description for the LLM
    - input_schema: JSON schema for tool input validation
    - execute(): The actual tool logic
    
    Design pattern: Template Method + Strategy
    - Subclasses implement specific tool logic in execute()
    - Base class handles permission checks, input validation, error handling
    
    Example:
        class ReadTool(Tool):
            name = "read"
            description = "Read contents from a file"
            
            def get_input_schema(self) -> Dict[str, Any]:
                return {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path to read"}
                    },
                    "required": ["path"]
                }
            
            async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
                path = input_data["path"]
                # ... implementation
    """

    # ------------------------------------------------------------------
    # Class-level attributes (override in subclasses)
    # ------------------------------------------------------------------

    name: str = ""
    """Unique identifier for this tool (e.g., 'bash', 'read', 'glob')."""

    description: str = ""
    """Human-readable description explaining what this tool does. 
    Used by the LLM to decide when to call this tool."""

    # ------------------------------------------------------------------
    # Permission model
    # ------------------------------------------------------------------

    permission: Permission = field(default_factory=Permission)
    """Permission configuration for this tool."""

    # ------------------------------------------------------------------
    # Abstract methods (must override)
    # ------------------------------------------------------------------

    @abstractmethod
    def get_input_schema(self) -> Dict[str, Any]:
        """
        Return the JSON schema for this tool's input.
        
        This schema is sent to the LLM so it knows how to call the tool.
        Uses JSON Schema draft-07 format.
        
        Returns:
            Dict representing a JSON Schema for the tool input.
            
        Example:
            {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to read"
                    },
                    "line_numbers": {
                        "type": "boolean",
                        "description": "Show line numbers",
                        "default": False
                    }
                },
                "required": ["path"]
            }
        """
        raise NotImplementedError

    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """
        Execute the tool with the given input.
        
        This is the main entry point for tool execution.
        Override this method in subclasses to implement tool logic.
        
        Args:
            input_data: Validated input matching get_input_schema()
            
        Returns:
            ToolResult with success status, content, and optional metadata
            
        Note:
            This is async to support both synchronous and asynchronous tools.
            Synchronous tools can simply return await asyncio.to_thread(...)
            or just return ToolResult.ok(...) directly.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Concrete methods (generally not overridden)
    # ------------------------------------------------------------------

    def get_metadata(self) -> Dict[str, Any]:
        """
        Return tool metadata for registration and LLM tool definitions.
        
        Returns:
            Dict containing name, description, and input_schema for the LLM.
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.get_input_schema(),
        }

    def validate_input(self, input_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate input data against the tool's input schema.
        
        Uses simple type checking based on JSON Schema types.
        For full schema validation, use an external library like jsonschema.
        
        Args:
            input_data: The input data to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        schema = self.get_input_schema()
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        # Check required fields
        for field_name in required:
            if field_name not in input_data:
                return False, f"Missing required field: {field_name}"

        # Check field types
        for field_name, value in input_data.items():
            if field_name in properties:
                expected_type = properties[field_name].get("type")
                if expected_type and not self._check_type(value, expected_type):
                    return False, f"Field '{field_name}' must be of type {expected_type}"

        return True, None

    @staticmethod
    def _check_type(value: Any, expected_type: str) -> bool:
        """Check if a value matches an expected JSON schema type."""
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "object": dict,
            "array": list,
            "null": type(None),
        }
        expected = type_map.get(expected_type)
        if expected is None:
            return True  # Unknown type, skip validation
        return isinstance(value, expected)

    def check_permission(self) -> tuple[bool, Optional[str]]:
        """
        Check if the tool execution is permitted.
        
        Returns:
            Tuple of (is_allowed, reason_if_denied)
        """
        if self.permission.mode == PermissionMode.NEVER:
            return False, f"Tool '{self.name}' is disabled (NEVER permission)"

        # Path-based permission check (simplified)
        # Full implementation would check actual paths against allowed/denied lists
        return True, None

    def __repr__(self) -> str:
        return f"<Tool name={self.name} mode={self.permission.mode.value}>"
