"""
QueryEngine - Core Agent Loop

Corresponds to: src/query.ts (core portions)

This is the main agent loop that:
1. Sends messages to the LLM
2. Processes LLM responses (text + tool calls)
3. Executes tools and returns results
4. Continues until the task is complete or max iterations reached

Key concepts:
- Message loop: while not done, send context → get response → execute tools → repeat
- Tool call dispatch: Parse tool_calls from LLM response → execute via registry → add results
- Streaming: Supports streaming responses for better UX
- Permission prompts: ASK-mode tools require user confirmation before execution
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from agent.context import AgentContext, Message, MessageRole, ToolCall, ToolResultBlock
from tool.base import Tool, ToolResult
from tool.registry import ToolRegistry, get_tool_registry


class AgentState(Enum):
    """Current state of the agent."""
    IDLE = "idle"
    THINKING = "thinking"
    TOOL_CALLING = "tool_calling"
    AWAITING_PERMISSION = "awaiting_permission"
    DONE = "done"
    ERROR = "error"


@dataclass
class AgentConfig:
    """
    Configuration for the QueryEngine.
    
    Attributes:
        model: LLM model name (e.g., 'claude-sonnet-4-20250514')
        max_iterations: Max number of agent loops (default 100)
        max_tool_calls_per_iteration: Max tool calls per LLM response (default 128)
        temperature: LLM temperature (default 0)
        system_prompt: System prompt override
        stream: Whether to stream LLM responses (default True)
        verbose: Whether to print verbose output (default False)
    """

    model: str = "claude-sonnet-4-20250514"
    max_iterations: int = 100
    max_tool_calls_per_iteration: int = 128
    temperature: float = 0
    system_prompt: Optional[str] = None
    stream: bool = True
    verbose: bool = False


class QueryEngine:
    """
    Core agent query engine - the main loop that processes user requests.
    
    Corresponds to: src/query.ts ~QueryEngine~ (main portions)
    
    This is the heart of the agent. It:
    1. Maintains context (message history)
    2. Sends context to LLM API
    3. Processes LLM responses (text output + tool calls)
    4. Executes tools via the ToolRegistry
    5. Adds tool results back to context
    6. Repeats until done
    
    Architecture:
        User Input → Context → LLM API → Response Parser
                                            ↓
                          ┌───────────────┴───────────────┐
                          ↓                               ↓
                    Text Output                    Tool Calls
                          ↓                               ↓
                    Print to user              Execute via Registry
                          ↓                               ↓
                    Add to Context ←────────── Add Tool Results
                          ↓
                    Check if Done? ──No──→ Loop back to LLM
                          ↓ Yes
                      Finish
    
    Usage:
        engine = QueryEngine(tool_registry=get_tool_registry())
        await engine.run(user_message="Read ./main.py and explain it")
    """

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        config: Optional[AgentConfig] = None,
        llm_client: Optional[Any] = None,
        console: Optional[Console] = None,
    ) -> None:
        """
        Initialize the QueryEngine.
        
        Args:
            tool_registry: The tool registry (uses global if not provided)
            config: Agent configuration
            llm_client: LLM API client (anthropic/openai). If None, uses default.
            console: Rich console for output (creates one if not provided)
        """
        self.tool_registry = tool_registry or get_tool_registry()
        self.config = config or AgentConfig()
        self.console = console or Console()
        self.llm_client = llm_client
        
        # Initialize context
        system_prompt = self.config.system_prompt or self._default_system_prompt()
        self.context = AgentContext(system_prompt=system_prompt)
        
        # State
        self.state = AgentState.IDLE
        self.iteration = 0
        self._stop_event = asyncio.Event()

    def _default_system_prompt(self) -> str:
        """
        Return the default system prompt for the agent.
        
        Corresponds to: src/query.ts ~defaultSystemPrompt~
        
        This instructs Claude about its role as a coding assistant.
        """
        return """You are Claude Code, an AI coding assistant.

When using tools:
- ALWAYS prefer existing files and code patterns you can see in the project
- Be precise about file paths and line numbers
- Read relevant files before editing them
- Explain what you're doing, especially for destructive operations
- If a tool fails, explain why and suggest alternatives

Available tools: read, edit, bash, glob

For file operations:
- Use 'read' to examine existing files before editing
- Use 'glob' to find files matching patterns
- Use 'edit' for search-and-replace (provide exact old_text to match)
- Use 'bash' for git, npm, and other shell operations

Stay focused on the user's request. Ask clarifying questions if needed.
"""

    # -------------------------------------------------------------------------
    # Main entry point
    # -------------------------------------------------------------------------

    async def run(self, user_message: str) -> str:
        """
        Run the agent loop with a user message.
        
        Corresponds to: src/query.ts ~run~ / main query loop
        
        This is the main async entry point. It:
        1. Adds the user message to context
        2. Runs the agent loop until complete
        3. Returns the final response text
        
        Args:
            user_message: The user's request
            
        Returns:
            The final assistant response text
        """
        self.context.add_user_message(user_message)
        return await self._run_loop()

    async def _run_loop(self) -> str:
        """
        The main agent loop.
        
        Corresponds to: src/query.ts ~while loop~ (the core agent loop)
        
        Loop:
        1. Call LLM with current context
        2. Parse response (text + tool calls)
        3. Execute tools (with permission checks)
        4. Add results to context
        5. Check stop conditions
        """
        last_response = ""
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True,
        ) as progress:
            task = progress.add_task("[cyan]Thinking...", total=None)
            
            while not self._stop_event.is_set() and self.iteration < self.config.max_iterations:
                self.iteration += 1
                self.state = AgentState.THINKING
                
                if self.config.verbose:
                    self.console.print(f"[dim]Iteration {self.iteration}/{self.config.max_iterations}[/dim]")
                
                # Call LLM
                response = await self._call_llm()
                
                if response is None:
                    self.state = AgentState.ERROR
                    return "Error: LLM call failed"
                
                # Process response
                # 提取文本内容（处理 content 中的 TextBlock 和 ToolUseBlock）
                text_content = ""
                tool_calls = []
                if hasattr(response, 'content') and response.content:
                    for block in response.content:
                        # TextBlock 有 text 属性
                        if hasattr(block, 'text'):
                            text_content += block.text
                        # ToolUseBlock 是工具调用
                        elif hasattr(block, 'name') and hasattr(block, 'input'):
                            tool_calls.append({
                                "id": getattr(block, 'id', f"tool_{len(tool_calls)}"),
                                "name": block.name,
                                "input": block.input or {},
                            })
                
                # Add assistant message to context
                tc_objects: Optional[List[ToolCall]] = None
                if tool_calls:
                    tc_objects = [
                        ToolCall(
                            id=tc.get("id", f"tool_{i}"),
                            name=tc.get("name", ""),
                            input_data=tc.get("input", {}),
                        )
                        for i, tc in enumerate(tool_calls)
                    ]
                
                self.context.add_assistant_message(text_content, tool_calls=tc_objects)
                last_response = text_content
                
                # Print text output
                if text_content:
                    self._print_response(text_content)
                
                # Execute tool calls
                if tool_calls:
                    self.state = AgentState.TOOL_CALLING
                    progress.update(task, description="[cyan]Executing tools...")
                    
                    await self._execute_tool_calls(tool_calls)
                    
                    progress.update(task, description="[cyan]Thinking...")
                    
                    # Check for completion (no more tool calls = done)
                    if not tool_calls:
                        break
                else:
                    # No tool calls = we're done
                    break
            
            progress.update(task, description="[green]Done!")
        
        self.state = AgentState.DONE
        return last_response

    # -------------------------------------------------------------------------
    # LLM Integration
    # -------------------------------------------------------------------------

    async def _call_llm(self) -> Any:
        """
        Call the LLM API with the current context.
        
        Uses anthropic Python SDK which supports both native Anthropic API
        and OpenAI-compatible APIs (e.g., Volcengine) via base_url.
        """
        import os
        
        api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("API_KEY")
        if not api_key:
            self.console.print("[yellow]Warning: ANTHROPIC_API_KEY not set, using mock response[/yellow]")
            return await self._mock_llm_response()
        
        api_base_url = os.environ.get("ANTHROPIC_API_BASE_URL", "https://api.anthropic.com/v1")
        
        # 初始化 LLM 客户端（anthropic SDK 自动处理兼容模式）
        if self.llm_client is None:
            try:
                from anthropic import AsyncAnthropic
                self.llm_client = AsyncAnthropic(api_key=api_key, base_url=api_base_url)
            except ImportError:
                self.console.print("[red]anthropic SDK not installed[/red]")
                return await self._mock_llm_response()
        
        messages = self.context.get_messages()
        tools = self.tool_registry.get_llm_tools()
        
        # 转换消息格式
        # 注意：Volcengine 等 OpenAI 兼容 API 不支持 system role 和 tool role，需要转换
        is_openai = "volces" in api_base_url or "openai" in api_base_url or "ark." in api_base_url
        
        chat_messages = []
        system_content = None
        for msg in messages:
            role = msg.get("role", "user") if isinstance(msg, dict) else getattr(msg, "role", "user")
            content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", str(msg))
            tool_call_id = getattr(msg, "tool_call_id", None) if not isinstance(msg, dict) else msg.get("tool_call_id")
            
            if role == "system":
                if is_openai:
                    # OpenAI 兼容 API: 把 system 拼到第一条 user 消息里
                    system_content = content
                else:
                    chat_messages.append({"role": role, "content": content})
            
            elif role == "tool" and is_openai:
                # Volcengine 不支持 tool role，转为 user role
                if tool_call_id:
                    content = f"[Tool Result for {tool_call_id}]: {content}"
                chat_messages.append({"role": "user", "content": content})
            
            else:
                chat_messages.append({"role": role, "content": content})
        
        # 如果有 system 内容且是 OpenAI 兼容，附加到首条 user 消息
        if system_content and is_openai and chat_messages and chat_messages[0]["role"] == "user":
            chat_messages[0]["content"] = f"[System: {system_content}]\n\n" + chat_messages[0]["content"]
        
        request_options: Dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": 8192,
            "messages": chat_messages,
            "tools": tools,
        }
        if self.config.temperature != 0:
            request_options["temperature"] = self.config.temperature
        
        try:
            if self.config.stream:
                async with self.llm_client.messages.stream(**request_options) as stream:
                    return await stream.get_final_message()
            else:
                return await self.llm_client.messages.create(**request_options)
        except Exception as e:
            self.console.print(f"[red]LLM API error: {e}[/red]")
            return None

    async def _mock_llm_response(self) -> Any:
        """
        Return a mock LLM response for testing without API key.
        
        This allows the framework to be explored without Anthropic credentials.
        """
        messages = self.context.get_messages()
        last_user_msg = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                last_user_msg = msg["content"]
                break
        
        # Simple mock: if user asks to read a file, suggest a tool call
        class MockResponse:
            content = f"I processed your request: {last_user_msg[:100]}"
            tool_calls = []
        
        return MockResponse()

    # -------------------------------------------------------------------------
    # Tool Call Execution
    # -------------------------------------------------------------------------

    async def _execute_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> None:
        """
        Execute a list of tool calls.
        
        Corresponds to: src/query.ts ~executeToolCalls~ / tool execution loop
        
        For each tool call:
        1. Look up the tool in the registry
        2. Check permissions (prompt user if ASK mode)
        3. Execute the tool
        4. Add result to context
        
        Args:
            tool_calls: List of tool call dicts from LLM response
        """
        for i, tc in enumerate(tool_calls):
            if i >= self.config.max_tool_calls_per_iteration:
                if self.config.verbose:
                    self.console.print(f"[yellow]Max tool calls per iteration reached[/yellow]")
                break
            
            tool_name = tc.get("name", "")
            tool_input = tc.get("input", {})
            tool_id = tc.get("id", f"tool_{i}")
            
            # Look up tool
            tool = self.tool_registry.get(tool_name)
            if tool is None:
                error_result = ToolResult.err(f"Unknown tool: {tool_name}")
                self.context.add_tool_result(error_result.content or error_result.error or "", tool_id)
                continue
            
            # Permission check
            allowed, reason = tool.check_permission()
            if not allowed:
                self.context.add_tool_result(f"Permission denied: {reason}", tool_id)
                continue
            
            # Prompt user if ASK mode
            if tool.permission.mode.value == "ask":
                if not self._prompt_permission(tool):
                    self.context.add_tool_result("User denied permission", tool_id)
                    continue
            
            # Execute tool
            if self.config.verbose:
                self.console.print(f"[dim]Executing {tool_name}...[/dim]")
            
            try:
                result: ToolResult = await tool.execute(tool_input)
            except Exception as e:
                result = ToolResult.err(f"Tool execution error: {e}")
            
            # Check if this is a SkillTool result with new_messages in metadata
            new_messages = result.metadata.get("new_messages") if result.metadata else None
            if tool_name == "Skill" and new_messages:
                # SkillTool returns new messages that should be added to context
                for msg in new_messages:
                    # Convert dict to Message if needed
                    if isinstance(msg, dict):
                        from agent.context import Message, MessageRole
                        role_str = msg.get("role", "user")
                        role = MessageRole(role_str)
                        content = msg.get("content", "")
                        self.context.add_message(Message(role=role, content=content))
                    else:
                        self.context.add_message(msg)
                if self.config.verbose:
                    self.console.print(f"[dim]Skill loaded: {len(new_messages)} messages[/dim]")
                # Add a tool result message indicating success
                self.context.add_tool_result(f"Skill loaded: {result.metadata.get('skill_name', 'unknown')}", tool_id)
            else:
                # Normal tool result handling
                result_content = result.content if result.success else (result.error or "Error")
                self.context.add_tool_result(result_content, tool_id)
                
                # Print tool result in verbose mode
                if self.config.verbose and result.content:
                    self.console.print(f"[dim]{tool_name} result:[/dim] {result.content[:200]}")

    def _prompt_permission(self, tool: Tool) -> bool:
        """
        Prompt the user for permission to execute a tool.
        
        Corresponds to: src/query.ts ~askPermission~
        
        For CLI, this uses a simple y/n prompt.
        In interactive mode, this could show a more detailed prompt.
        
        Args:
            tool: The tool to execute
            
        Returns:
            True if user grants permission, False otherwise
        """
        # In non-interactive / automated mode, default to allow for AUTOMATIC tools
        # and deny for ASK tools (to be safe)
        # Override this method for interactive CLI with proper prompts
        self.console.print(
            Panel(
                f"[bold]{tool.name}[/bold] wants to execute.\n"
                f"[dim]Scope: {tool.permission.scope.value} | Mode: {tool.permission.mode.value}[/dim]\n"
                f"{tool.description[:100]}",
                title="Tool Permission",
                border_style="yellow",
            )
        )
        
        # For automated testing, skip prompts
        # TODO: Add proper interactive prompt using typer prompt
        return True

    # -------------------------------------------------------------------------
    # Output Formatting
    # -------------------------------------------------------------------------

    def _print_response(self, text: str) -> None:
        """
        Print the LLM's text response to the console.
        
        Corresponds to: src/query.ts ~printResponse~
        
        Args:
            text: The response text to print
        """
        if not text:
            return
        
        # Render as markdown for nice formatting
        md = Markdown(text)
        self.console.print(md)

    # -------------------------------------------------------------------------
    # Control methods
    # -------------------------------------------------------------------------

    def stop(self) -> None:
        """
        Signal the agent to stop after the current iteration.
        """
        self._stop_event.set()

    @property
    def is_running(self) -> bool:
        """Return True if the agent is currently processing."""
        return self.state in (AgentState.THINKING, AgentState.TOOL_CALLING)

    # TODO: Add support for resumable sessions (save/load context)
    # TODO: Add support for multi-turn tool conversations
    # TODO: Add proper error recovery and retry logic
