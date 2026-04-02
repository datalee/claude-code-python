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
from tool.builtin.send_message import SendMessageTool
from tool.builtin.notebook_edit import NotebookEditTool
from tool.builtin.powershell import PowerShellTool
from tool.builtin.tool_search import ToolSearchTool
from tool.builtin.brief import BriefTool
from tool.builtin.team_create import TeamCreateTool
from tool.builtin.remote_trigger import RemoteTriggerTool
from tool.builtin.list_mcp_resources import ListMcpResourcesTool
from tool.builtin.read_mcp_resource import ReadMcpResourceTool
from tool.builtin.mcp_auth import McpAuthTool

__all__ = [
    "BashTool",
    "FileReadTool",
    "FileEditTool",
    "GlobTool",
    "ConfigTool",
    "AskUserQuestionTool",
    "TodoWriteTool",
    "SendMessageTool",
    "NotebookEditTool",
    "PowerShellTool",
    "ToolSearchTool",
    "BriefTool",
    "TeamCreateTool",
    "RemoteTriggerTool",
    "ListMcpResourcesTool",
    "ReadMcpResourceTool",
    "McpAuthTool",
]

# Auto-register all builtin tools when this module is imported
def _register_builtin_tools() -> None:
    """Register all built-in tools with the global registry."""
    from tool.registry import get_tool_registry
    
    registry = get_tool_registry()
    for tool_class in [BashTool, FileReadTool, FileEditTool, GlobTool, ConfigTool, AskUserQuestionTool, TodoWriteTool, SendMessageTool, NotebookEditTool, PowerShellTool, ToolSearchTool, BriefTool, TeamCreateTool, RemoteTriggerTool, ListMcpResourcesTool, ReadMcpResourceTool, McpAuthTool]:
        try:
            registry.register(tool_class())
        except ValueError:
            # Already registered (e.g., during re-import)
            pass


# Note: Auto-registration is disabled by default to allow selective registration.
# Enable by calling _register_builtin_tools() in main.py or explicitly.
