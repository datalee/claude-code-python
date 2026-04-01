"""
Schemas Module - JSON Schema 定义

用于配置和数据验证的 JSON Schema。
对应 Claude Code 源码: src/schemas/*.ts
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

# ============================================================================
# Schema 定义
# ============================================================================

# Agent 配置 Schema
AGENT_CONFIG_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "model": {
            "type": "string",
            "description": "Model name to use",
            "default": "claude-sonnet-4-20250514",
        },
        "max_tokens": {
            "type": "integer",
            "minimum": 1,
            "maximum": 8192,
            "default": 4096,
            "description": "Maximum tokens in response",
        },
        "temperature": {
            "type": "number",
            "minimum": 0,
            "maximum": 2,
            "default": 1.0,
            "description": "Sampling temperature",
        },
        "system_prompt": {
            "type": "string",
            "description": "System prompt override",
        },
        "permission_mode": {
            "type": "string",
            "enum": ["safe", "ask", "auto", "off"],
            "default": "safe",
            "description": "Permission mode",
        },
    },
    "additionalProperties": False,
}

# Config Schema
CONFIG_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "version": {
            "type": "string",
            "description": "Config version",
        },
        "model": {
            "type": "string",
            "description": "Default model",
        },
        "permission_mode": {
            "type": "string",
            "enum": ["safe", "ask", "auto", "off"],
        },
        "memory_enabled": {
            "type": "boolean",
            "default": True,
        },
        "hooks_enabled": {
            "type": "boolean",
            "default": True,
        },
        "auto_compact": {
            "type": "boolean",
            "default": True,
        },
        "compact_threshold_tokens": {
            "type": "integer",
            "minimum": 10000,
            "maximum": 500000,
            "default": 100000,
        },
        "max_tokens": {
            "type": "integer",
            "minimum": 1,
            "maximum": 8192,
        },
        "temperature": {
            "type": "number",
            "minimum": 0,
            "maximum": 2,
        },
    },
    "additionalProperties": False,
}

# Memory Entry Schema
MEMORY_ENTRY_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["name", "type"],
    "properties": {
        "name": {
            "type": "string",
            "description": "Memory name",
        },
        "description": {
            "type": "string",
            "description": "Memory description",
        },
        "type": {
            "type": "string",
            "enum": ["user", "project", "reference", "diary", "longterm"],
            "description": "Memory type",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Memory tags",
        },
        "created": {
            "type": "string",
            "format": "date-time",
            "description": "Creation timestamp",
        },
        "modified": {
            "type": "string",
            "format": "date-time",
            "description": "Last modified timestamp",
        },
        "content": {
            "type": "string",
            "description": "Memory content (body, after frontmatter)",
        },
    },
    "additionalProperties": True,
}

# Hook Config Schema
HOOK_CONFIG_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "enabled": {
            "type": "boolean",
            "default": True,
        },
        "async_execute": {
            "type": "boolean",
            "default": True,
            "description": "Execute hooks asynchronously",
        },
        "retry_count": {
            "type": "integer",
            "minimum": 0,
            "maximum": 5,
            "default": 3,
        },
        "timeout_ms": {
            "type": "integer",
            "minimum": 100,
            "maximum": 60000,
            "default": 5000,
        },
    },
    "additionalProperties": False,
}

# Plugin Manifest Schema
PLUGIN_MANIFEST_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["name", "version"],
    "properties": {
        "name": {
            "type": "string",
            "pattern": "^[a-z0-9_]+$",
            "description": "Plugin name (lowercase, no spaces)",
        },
        "version": {
            "type": "string",
            "pattern": "^\\d+\\.\\d+\\.\\d+$",
            "description": "Semantic version",
        },
        "description": {
            "type": "string",
        },
        "author": {
            "type": "string",
        },
        "main": {
            "type": "string",
            "description": "Entry point file",
        },
        "dependencies": {
            "type": "array",
            "items": {"type": "string"},
        },
        "permissions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Required permissions",
        },
        "events": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Subscribed events",
        },
    },
    "additionalProperties": False,
}


# ============================================================================
# Schema 工具函数
# ============================================================================

def get_schema(name: str) -> Optional[Dict[str, Any]]:
    """
    按名称获取 Schema。
    
    Args:
        name: Schema 名称
        
    Returns:
        Schema 定义，或 None
    """
    schemas = {
        "agent_config": AGENT_CONFIG_SCHEMA,
        "config": CONFIG_SCHEMA,
        "memory_entry": MEMORY_ENTRY_SCHEMA,
        "hook_config": HOOK_CONFIG_SCHEMA,
        "plugin_manifest": PLUGIN_MANIFEST_SCHEMA,
    }
    return schemas.get(name)


def validate(data: Any, schema_name: str) -> tuple[bool, Optional[str]]:
    """
    验证数据是否符合 Schema。
    
    Args:
        data: 要验证的数据
        schema_name: Schema 名称
        
    Returns:
        (是否有效, 错误信息)
    """
    # 简单验证 - 实际使用 jsonschema 库会更好
    schema = get_schema(schema_name)
    if not schema:
        return False, f"Unknown schema: {schema_name}"
    
    # 检查必需字段
    required = schema.get("required", [])
    if isinstance(data, dict):
        for field in required:
            if field not in data:
                return False, f"Missing required field: {field}"
    
    return True, None


def validate_memory_entry(entry: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """验证记忆条目"""
    return validate(entry, "memory_entry")


def validate_config(config: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """验证配置"""
    return validate(config, "config")


def validate_plugin_manifest(manifest: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """验证插件清单"""
    return validate(manifest, "plugin_manifest")


# ============================================================================
# 导出 JSON Schema
# ============================================================================

def export_schema(schema_name: str, output_file: Optional[str] = None) -> str:
    """
    导出 Schema 为 JSON 字符串。
    
    Args:
        schema_name: Schema 名称
        output_file: 可选，输出文件路径
        
    Returns:
        JSON 字符串
    """
    schema = get_schema(schema_name)
    if not schema:
        raise ValueError(f"Unknown schema: {schema_name}")
    
    json_str = json.dumps(schema, indent=2)
    
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(json_str)
    
    return json_str


def export_all_schemas(output_dir: str) -> None:
    """
    导出所有 Schema 到指定目录。
    
    Args:
        output_dir: 输出目录
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    schemas = [
        ("agent_config", "agent-config.schema.json"),
        ("config", "config.schema.json"),
        ("memory_entry", "memory-entry.schema.json"),
        ("hook_config", "hook-config.schema.json"),
        ("plugin_manifest", "plugin-manifest.schema.json"),
    ]
    
    for schema_name, filename in schemas:
        output_path = os.path.join(output_dir, filename)
        export_schema(schema_name, output_path)


__all__ = [
    # Schema 定义
    "AGENT_CONFIG_SCHEMA",
    "CONFIG_SCHEMA",
    "MEMORY_ENTRY_SCHEMA",
    "HOOK_CONFIG_SCHEMA",
    "PLUGIN_MANIFEST_SCHEMA",
    # 工具函数
    "get_schema",
    "validate",
    "validate_memory_entry",
    "validate_config",
    "validate_plugin_manifest",
    "export_schema",
    "export_all_schemas",
]
