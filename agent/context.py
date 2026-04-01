"""
Context Management

Corresponds to: src/context.ts

Manages the conversation context / message history for the agent.
Handles:
- Message history (user messages, assistant responses, tool results)
- Context limits (token budgeting)
- Message formatting for LLM API
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import tiktoken


class MessageRole(Enum):
    """
    Role types for messages in the conversation.
    
    Corresponds to: src/context.ts ~Role~
    
    - system: System prompt / instructions
    - user: User messages
    - assistant: Assistant (LLM) responses
    - tool: Results from tool executions
    """

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """
    A single message in the conversation history.
    
    Corresponds to: src/context.ts ~Message~ interface
    
    Attributes:
        role: Who is speaking (system/user/assistant/tool)
        content: The text content of the message
        tool_calls: Optional list of tool calls made in this message
        tool_call_id: ID of the tool call this message is responding to (for role=tool)
        name: Name of the tool (for role=tool)
        timestamp: Unix timestamp when the message was created
    """

    role: MessageRole
    content: str = ""
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for API calls."""
        result: Dict[str, Any] = {
            "role": self.role.value,
            "content": self.content,
        }
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        if self.name:
            result["name"] = self.name
        return result


@dataclass
class ToolCall:
    """
    Represents a single tool invocation.
    
    Corresponds to: src/context.ts ~ToolCall~ interface
    
    Attributes:
        id: Unique ID for this tool call
        name: Name of the tool being called
        input_data: The input arguments to the tool
    """

    id: str
    name: str
    input_data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "input": self.input_data,
        }


@dataclass
class ToolResultBlock:
    """
    A tool result block for tool_call message content.
    
    Corresponds to: src/context.ts ~ToolResultBlock~
    
    Attributes:
        type: Always "tool_result"
        tool_use_id: ID of the tool call this result is for
        content: The result content (text or error)
    """

    type: str = "tool_result"
    tool_use_id: str = ""
    content: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "tool_use_id": self.tool_use_id,
            "content": self.content,
        }


class AgentContext:
    """
    Manages conversation context and message history.
    
    Corresponds to: src/context.ts ~Context~ class
    
    Responsibilities:
    - Store and manage message history
    - Format messages for LLM API
    - Track token usage (approximate)
    - Handle context window limits
    
    Design notes:
    - Messages are stored in order (oldest first)
    - System message is kept separate for easy insertion
    - Token counting uses tiktoken (cl100k_base for Claude-compatible)
    
    Example:
        ctx = AgentContext()
        
        # Add messages
        ctx.add_user_message("Read the file at ./main.py")
        ctx.add_assistant_message("...", tool_calls=[...])
        ctx.add_tool_result("file content here", tool_call_id="tool_1")
        
        # Get formatted messages for API
        api_messages = ctx.get_messages()
    """

    DEFAULT_MAX_TOKENS = 200_000  # Claude's context window (approximate)
    TOKEN_ESTIMATE_CHARS = 4  # 1 token ≈ 4 chars in English

    def __init__(
        self,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> None:
        """
        Initialize a new context.
        
        Args:
            system_prompt: Optional initial system message
            max_tokens: Maximum tokens in context (approximate)
        """
        self.max_tokens = max_tokens or self.DEFAULT_MAX_TOKENS
        self._messages: List[Message] = []
        self._tool_results: Dict[str, str] = {}  # tool_call_id -> content
        
        # Token counter (optional, requires tiktoken)
        self._encoder = None
        try:
            self._encoder = tiktoken.get_encoding("cl100k_base")
        except Exception:
            pass  # tiktoken not available, use character estimate

        if system_prompt:
            self.add_message(Message(role=MessageRole.SYSTEM, content=system_prompt))

    @property
    def messages(self) -> List[Message]:
        """Get all messages (read-only view)."""
        return list(self._messages)

    def add_message(self, message: Message) -> None:
        """
        Add a message to the context.
        
        Args:
            message: The message to add
        """
        self._messages.append(message)

    def add_user_message(self, content: str) -> None:
        """
        Add a user message.
        
        Args:
            content: The user's message text
        """
        self.add_message(Message(role=MessageRole.USER, content=content))

    def add_assistant_message(
        self,
        content: str,
        tool_calls: Optional[List[ToolCall]] = None,
    ) -> None:
        """
        Add an assistant message (LLM response).
        
        Args:
            content: The assistant's response text
            tool_calls: Optional list of tool calls made by this message
        """
        tc_dicts: Optional[List[Dict[str, Any]]] = None
        if tool_calls:
            tc_dicts = [tc.to_dict() for tc in tool_calls]
        self.add_message(Message(role=MessageRole.ASSISTANT, content=content, tool_calls=tc_dicts))

    def add_tool_result(self, content: str, tool_call_id: str) -> None:
        """
        Add a tool result message.
        
        Args:
            content: The result of the tool execution
            tool_call_id: ID of the tool call this is a result for
        """
        self._tool_results[tool_call_id] = content
        self.add_message(
            Message(
                role=MessageRole.TOOL,
                content=content,
                tool_call_id=tool_call_id,
            )
        )

    def get_messages(self) -> List[Dict[str, Any]]:
        """
        Get all messages formatted for the LLM API.
        
        Returns:
            List of message dicts with 'role' and 'content' keys.
            Tool results are included inline in assistant messages.
        """
        return [msg.to_dict() for msg in self._messages]

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        
        Uses tiktoken if available, otherwise falls back to char/4 estimate.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Estimated number of tokens
        """
        if self._encoder:
            return len(self._encoder.encode(text))
        return len(text) // self.TOKEN_ESTIMATE_CHARS

    def estimate_total_tokens(self) -> int:
        """
        Estimate total tokens in context.
        
        Returns:
            Estimated total token count
        """
        total = 0
        for msg in self._messages:
            total += self.estimate_tokens(msg.content)
        return total

    def truncate_if_needed(self, keep_recent: int = 20) -> List[Message]:
        """
        Truncate messages if context is getting too large.
        
        Keeps the system message + most recent messages.
        
        Args:
            keep_recent: Number of recent non-system messages to keep
            
        Returns:
            List of removed messages (for potential retrieval)
        """
        removed: List[Message] = []
        while self.estimate_total_tokens() > self.max_tokens and len(self._messages) > 2:
            # Remove oldest non-system message
            for i, msg in enumerate(self._messages):
                if msg.role != MessageRole.SYSTEM:
                    removed.append(self._messages.pop(i))
                    break
        
        return removed

    def clear(self) -> None:
        """Clear all messages except system message."""
        system_messages = [m for m in self._messages if m.role == MessageRole.SYSTEM]
        self._messages = system_messages
        self._tool_results.clear()

    def __len__(self) -> int:
        return len(self._messages)

    def __repr__(self) -> str:
        return f"<AgentContext messages={len(self._messages)} tokens≈{self.estimate_total_tokens()}>"
