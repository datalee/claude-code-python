"""
Built-in Tool Implementations

These tools provide the core file system and shell operations for the agent.
"""

from tool.builtin.bash import BashTool
from tool.builtin.file_read import FileReadTool
from tool.builtin.file_edit import FileEditTool
from tool.builtin.glob import GlobTool
from tool.builtin.config_tool import ConfigTool
from tool.builtin.ask_user_question import AskUserQuestionTool
from tool.builtin.todo_write import TodoWriteTool

__all__ = [
    "BashTool",
    "FileReadTool",
    "FileEditTool",
    "GlobTool",
    "ConfigTool",
    "AskUserQuestionTool",
    "TodoWriteTool",
]

# Auto-register all builtin tools when this module is imported
def _register_builtin_tools() -> None:
    """Register all built-in tools with the global registry."""
    from tool.registry import get_tool_registry
    
    registry = get_tool_registry()
    for tool_class in [BashTool, FileReadTool, FileEditTool, GlobTool, ConfigTool, AskUserQuestionTool, TodoWriteTool]:
        try:
            registry.register(tool_class())
        except ValueError:
            # Already registered (e.g., during re-import)
            pass


# Note: Auto-registration is disabled by default to allow selective registration.
# Enable by calling _register_builtin_tools() in main.py or explicitly.
