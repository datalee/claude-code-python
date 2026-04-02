"""
Constants Module - 常量定义

项目全局常量。
对应 Claude Code 源码: src/constants/*.ts
"""

from __future__ import annotations

import os

# ============================================================================
# 版本信息
# ============================================================================

__version__ = "1.0.0"
__author__ = "Claude Code Python Team"

# ============================================================================
# API 配置
# ============================================================================

# Anthropic API - 支持环境变量覆盖
ANTHROPIC_API_BASE_URL = os.environ.get("ANTHROPIC_API_BASE_URL", "https://api.anthropic.com/v1")
ANTHROPIC_API_VERSION = "2023-06-01"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("API_KEY")

# 默认模型
DEFAULT_MODEL = "claude-sonnet-4-20250514"
FALLBACK_MODEL = "claude-haiku-4-20250514"

# Token 限制
DEFAULT_MAX_TOKENS = 4096
MAX_TOKENS_LIMIT = 8192

# ============================================================================
# 目录配置
# ============================================================================

# 默认配置目录
DEFAULT_CONFIG_DIR = "~/.claude"
DEFAULT_MEMORY_DIR = "~/.claude/memory"
DEFAULT_LOGS_DIR = "~/.claude/logs"
DEFAULT_PLUGINS_DIR = "~/.claude/plugins"
DEFAULT_HISTORY_FILE = "~/.claude/history.jsonl"

# ============================================================================
# Agent 配置
# ============================================================================

# 默认温度
DEFAULT_TEMPERATURE = 1.0

# 上下文窗口警告阈值
CONTEXT_WARNING_RATIO = 0.8  # 80% 时警告
CONTEXT_ERROR_RATIO = 0.95  # 95% 时错误

# 压缩阈值
DEFAULT_COMPACT_THRESHOLD = 100000  # tokens
MAX_COMPACT_THRESHOLD = 200000

# ============================================================================
# 权限模式
# ============================================================================

class PermissionMode:
    """权限模式"""
    SAFE = "safe"           # 安全模式，禁止危险操作
    ASK = "ask"             # 询问模式，每次确认
    AUTO = "auto"           # 自动模式，自动批准
    OFF = "off"            # 关闭权限检查（不推荐）

# 危险操作列表
DANGEROUS_OPERATIONS = [
    "delete",
    "drop",
    "remove",
    "rm",
    "uninstall",
    "format",
    "shutdown",
    "reboot",
]

# ============================================================================
# 工具配置
# ============================================================================

# BashTool 超时
DEFAULT_BASH_TIMEOUT = 60  # 秒
MAX_BASH_TIMEOUT = 3600   # 1 小时

# 文件操作限制
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = [
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
    ".kt", ".scala", ".r", ".R", ".m", ".lua", ".pl", ".sh",
    ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd",
    ".json", ".yaml", ".yml", ".toml", ".xml", ".html", ".css",
    ".md", ".txt", ".rst", ".tex", ".pdf",
    ".sql", ".graphql", ".proto", ".thrift",
    ".dockerfile", ".gitignore", ".env", ".editorconfig",
]

# ============================================================================
# Hook 事件
# ============================================================================

GATEWAY_EVENTS = [
    "gateway:startup",
    "gateway:shutdown",
]

COMMAND_EVENTS = [
    "command:new",
    "command:reset",
    "command:quit",
    "command:custom",
]

SESSION_EVENTS = [
    "session:start",
    "session:end",
    "session:resume",
]

COMPACTION_EVENTS = [
    "compaction:before",
    "compaction:after",
]

TOOL_EVENTS = [
    "tool:before",
    "tool:after",
    "tool:error",
]

ALL_EVENTS = (
    GATEWAY_EVENTS +
    COMMAND_EVENTS +
    SESSION_EVENTS +
    COMPACTION_EVENTS +
    TOOL_EVENTS
)

# ============================================================================
# 消息类型
# ============================================================================

class MessageType:
    TEXT = "text"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    THINKING = "thinking"

class MessageRole:
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

# ============================================================================
# 状态值
# ============================================================================

class AgentStatus:
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    ERROR = "error"
    DONE = "done"

class ExitCode:
    SUCCESS = 0
    USER_INTERRUPT = 130
    ERROR = 1
    TIMEOUT = 124

# ============================================================================
# 网络配置
# ============================================================================

DEFAULT_REMOTE_PORT = 8765
DEFAULT_REMOTE_HOST = "127.0.0.1"

# ============================================================================
# 日志配置
# ============================================================================

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

DEFAULT_LOG_LEVEL = "INFO"
DEBUG_LOG_LEVEL = "DEBUG"

# ============================================================================
# 兼容性
# ============================================================================

# Python 版本要求
MIN_PYTHON_VERSION = (3, 10)

# 必需依赖
REQUIRED_PACKAGES = [
    "anthropic",
]

OPTIONAL_PACKAGES = [
    "tiktoken",
    "typer",
    "rich",
]

__all__ = [
    # 版本
    "__version__",
    "__author__",
    # API
    "ANTHROPIC_API_BASE_URL",
    "ANTHROPIC_API_VERSION",
    "DEFAULT_MODEL",
    "FALLBACK_MODEL",
    "DEFAULT_MAX_TOKENS",
    "MAX_TOKENS_LIMIT",
    # 目录
    "DEFAULT_CONFIG_DIR",
    "DEFAULT_MEMORY_DIR",
    "DEFAULT_LOGS_DIR",
    "DEFAULT_PLUGINS_DIR",
    "DEFAULT_HISTORY_FILE",
    # Agent
    "DEFAULT_TEMPERATURE",
    "CONTEXT_WARNING_RATIO",
    "CONTEXT_ERROR_RATIO",
    "DEFAULT_COMPACT_THRESHOLD",
    "MAX_COMPACT_THRESHOLD",
    # 权限
    "PermissionMode",
    "DANGEROUS_OPERATIONS",
    # 工具
    "DEFAULT_BASH_TIMEOUT",
    "MAX_BASH_TIMEOUT",
    "MAX_FILE_SIZE",
    "ALLOWED_EXTENSIONS",
    # 事件
    "ALL_EVENTS",
    "GATEWAY_EVENTS",
    "COMMAND_EVENTS",
    "SESSION_EVENTS",
    "COMPACTION_EVENTS",
    "TOOL_EVENTS",
    # 消息
    "MessageType",
    "MessageRole",
    # 状态
    "AgentStatus",
    "ExitCode",
    # 网络
    "DEFAULT_REMOTE_PORT",
    "DEFAULT_REMOTE_HOST",
    # 日志
    "LOG_FORMAT",
    "LOG_DATE_FORMAT",
    "DEFAULT_LOG_LEVEL",
    "DEBUG_LOG_LEVEL",
    # 版本要求
    "MIN_PYTHON_VERSION",
    "REQUIRED_PACKAGES",
    "OPTIONAL_PACKAGES",
]
