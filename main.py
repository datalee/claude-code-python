#!/usr/bin/env python3
"""
Claude Code Python - CLI 入口

重构后的 CLI，支持：
- 单次任务模式（默认）
- 交互式 REPL 模式
- 会话管理
- 配置加载
- Hook 初始化

对应 Claude Code 源码: src/main.tsx
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.traceback import install

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed

# Install rich traceback handler
install(show_locals=True)

# Import agent components
from agent.query_engine import AgentConfig, QueryEngine
from agent.repl import REPL, REPLConfig
from hook.registry import get_hook_registry
from hook.builtin import (
    SessionMemoryHook,
    CommandLoggerHook,
    BootMdHook,
)
from tool.base import Permission, PermissionMode, PermissionScope
from tool.registry import get_tool_registry
from tool.builtin import (
    BashTool,
    FileReadTool,
    FileEditTool,
    GlobTool,
    ConfigTool,
    AskUserQuestionTool,
    TodoWriteTool,
    SendMessageTool,
    NotebookEditTool,
    PowerShellTool,
    ToolSearchTool,
    BriefTool,
    TeamCreateTool,
    RemoteTriggerTool,
    ListMcpResourcesTool,
    ReadMcpResourceTool,
    McpAuthTool,
    SyntheticOutputTool,
)
from tool.builtin.skill_tool import SkillTool

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="claude-code-python",
    help="Claude Code Python - An AI coding agent in Python",
    add_completion=False,
    rich_markup_mode="rich",
)

console = Console()


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

class Config:
    """全局配置"""
    
    def __init__(self):
        self.api_key: Optional[str] = None
        self.api_base_url: str = "https://api.anthropic.com/v1"
        self.model: str = "claude-sonnet-4-20250514"
        self.verbose: bool = False
        self.workspace_path: Path = Path.cwd()
        self.max_iterations: int = 100
        self.stream: bool = True
    
    @classmethod
    def from_env(cls) -> "Config":
        """从环境变量加载配置（.env 文件也会被 python-dotenv 自动加载）"""
        config = cls()
        config.api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("API_KEY")
        config.api_base_url = os.environ.get("ANTHROPIC_API_BASE_URL", config.api_base_url)
        config.model = os.environ.get("CLAUDE_CODE_MODEL", config.model)
        config.verbose = os.environ.get("CLAUDE_CODE_VERBOSE") == "1"
        config.max_iterations = int(os.environ.get("CLAUDE_CODE_MAX_ITERATIONS", "100"))
        return config


DEFAULT_SYSTEM_PROMPT = """You are Claude Code, an AI coding assistant.

You have access to tools for reading, editing, and executing code.
Always prefer using tools to accomplish the user's request efficiently.

Guidelines:
- Read files before editing them
- Use exact text matching for search-and-replace
- Use glob to find files when you don't know the exact path
- Use bash for git, npm, and build operations
- Explain your actions briefly
- If something fails, explain why and suggest alternatives
"""


# ---------------------------------------------------------------------------
# 工具注册
# ---------------------------------------------------------------------------

def register_builtin_tools() -> None:
    """
    注册所有内置工具。
    对应 Claude Code 源码: src/tools.ts
    """
    registry = get_tool_registry()
    
    # READ 权限工具 (只读，自动执行)
    read_tools = [
        (FileReadTool(), PermissionMode.AUTOMATIC, PermissionScope.READ),
        (GlobTool(), PermissionMode.AUTOMATIC, PermissionScope.READ),
        (ConfigTool(), PermissionMode.AUTOMATIC, PermissionScope.READ),
        (AskUserQuestionTool(), PermissionMode.AUTOMATIC, PermissionScope.READ),
        (ToolSearchTool(), PermissionMode.AUTOMATIC, PermissionScope.READ),
        (ListMcpResourcesTool(), PermissionMode.AUTOMATIC, PermissionScope.READ),
        (ReadMcpResourceTool(), PermissionMode.AUTOMATIC, PermissionScope.READ),
        (McpAuthTool(), PermissionMode.AUTOMATIC, PermissionScope.READ),
        (SkillTool(), PermissionMode.AUTOMATIC, PermissionScope.READ),
    ]
    
    # WRITE 权限工具 (需询问)
    write_tools = [
        (FileEditTool(), PermissionMode.ASK, PermissionScope.WRITE),
        (BashTool(), PermissionMode.ASK, PermissionScope.WRITE),
        (TodoWriteTool(), PermissionMode.ASK, PermissionScope.WRITE),
        (SendMessageTool(), PermissionMode.ASK, PermissionScope.WRITE),
        (NotebookEditTool(), PermissionMode.ASK, PermissionScope.WRITE),
        (PowerShellTool(), PermissionMode.ASK, PermissionScope.WRITE),
        (TeamCreateTool(), PermissionMode.ASK, PermissionScope.WRITE),
        (RemoteTriggerTool(), PermissionMode.ASK, PermissionScope.WRITE),
        (SyntheticOutputTool(), PermissionMode.ASK, PermissionScope.WRITE),
        (BriefTool(), PermissionMode.ASK, PermissionScope.WRITE),
    ]
    
    for tool, mode, scope in read_tools + write_tools:
        tool.permission = Permission(mode=mode, scope=scope)
        try:
            registry.register(tool)
        except ValueError:
            pass  # Already registered


def register_builtin_hooks() -> None:
    """
    注册所有内置钩子。
    对应 Claude Code 源码: src/hooks/index.ts
    """
    registry = get_hook_registry()
    
    # SessionMemoryHook - 保存会话上下文
    registry.register(SessionMemoryHook())
    
    # CommandLoggerHook - 记录命令日志
    registry.register(CommandLoggerHook())
    
    # BootMdHook - 启动时运行 BOOT.md
    registry.register(BootMdHook())


def initialize_system(config: Config) -> None:
    """
    初始化系统（工具 + 钩子）。
    """
    try:
        register_builtin_tools()
    except ValueError as e:
        if config.verbose:
            console.print(f"[dim]Tools already registered: {e}[/dim]")
    
    try:
        register_builtin_hooks()
    except ValueError as e:
        if config.verbose:
            console.print(f"[dim]Hooks already registered: {e}[/dim]")


# ---------------------------------------------------------------------------
# CLI 命令
# ---------------------------------------------------------------------------

@app.command()
def main(
    task: str = typer.Argument(
        None,
        help="The task for the agent. If not provided, enters REPL mode.",
    ),
    model: str = typer.Option(
        "claude-sonnet-4-20250514",
        "--model", "-m",
        help="LLM model to use",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Enable verbose output",
    ),
    max_iterations: int = typer.Option(
        100,
        "--max-iterations", "-n",
        help="Maximum number of agent loops",
    ),
    stream: bool = typer.Option(
        True,
        "--stream/--no-stream",
        help="Stream LLM responses",
    ),
    repl_mode: bool = typer.Option(
        False,
        "--repl",
        help="Force REPL mode even if task is provided",
    ),
) -> None:
    """
    运行 Claude Code Python。

    示例：
        python main.py "Read ./README.md"
        python main.py --repl
        echo "Read ./main.py" | python main.py
    """
    # 加载配置
    config = Config.from_env()
    config.model = model
    config.verbose = verbose
    config.max_iterations = max_iterations
    config.stream = stream
    
    # 检查 API key
    if not config.api_key:
        console.print(
            Panel(
                "[yellow]Warning: ANTHROPIC_API_KEY not set.[/yellow]\n"
                "The agent will run with mock responses.\n"
                "Set your API key with: export ANTHROPIC_API_KEY=sk-ant-...",
                title="API Key Missing",
                border_style="yellow",
            )
        )
    
    # 初始化系统
    initialize_system(config)
    
    # 创建 Engine
    engine_config = AgentConfig(
        model=config.model,
        max_iterations=config.max_iterations,
        stream=config.stream,
        verbose=config.verbose,
        system_prompt=DEFAULT_SYSTEM_PROMPT,
    )
    
    engine = QueryEngine(
        config=engine_config,
        console=console,
    )
    
    # 决定运行模式
    if task and not repl_mode:
        # 单次任务模式
        _run_task(engine, config, task)
    else:
        # REPL 模式
        asyncio.run(_run_repl(engine, config))


def _run_task(engine: QueryEngine, config: Config, task: str) -> None:
    """
    运行单次任务。
    """
    console.print(
        Panel(
            f"[bold cyan]Claude Code Python[/bold cyan]\n"
            f"[dim]Model:[/dim] {config.model}\n"
            f"[dim]Task:[/dim] {task[:60]}{'...' if len(task) > 60 else ''}",
            border_style="cyan",
        )
    )
    
    try:
        result = asyncio.run(engine.run(task))
        
        if engine.iteration >= config.max_iterations:
            console.print(f"\n[yellow]Max iterations ({config.max_iterations}) reached.[/yellow]")
        
        if config.verbose:
            console.print(f"\n[dim]Total iterations: {engine.iteration}[/dim]")
        
    except KeyboardInterrupt:
        engine.stop()
        console.print("\n[yellow]Interrupted by user[/yellow]")
        raise typer.Exit(code=130)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if config.verbose:
            import traceback
            traceback.print_exc()
        raise typer.Exit(code=1)


async def _run_repl(engine: QueryEngine, config: Config) -> None:
    """
    运行交互式 REPL。
    """
    repl_config = REPLConfig(
        quiet=False,
        history_file="~/.claude_code_history",
        history_size=1000,
    )
    
    repl = REPL(engine, config=repl_config)
    
    await repl.run()


@app.command("list-tools")
def list_tools() -> None:
    """
    列出所有可用工具。

    示例：
        python main.py list-tools
    """
    initialize_system(Config())
    registry = get_tool_registry()
    tools = registry.get_all_tools()
    
    console.print(f"\n[bold]Available tools ({len(tools)}):[/bold]\n")
    
    for tool in tools:
        console.print(
            Panel(
                f"[dim]Permission:[/dim] {tool.permission.mode.value} | "
                f"[dim]Scope:[/dim] {tool.permission.scope.value}\n\n"
                f"{tool.description}",
                title=f"[bold]{tool.name}[/bold]",
                border_style="cyan",
            )
        )


@app.command("list-hooks")
def list_hooks() -> None:
    """
    列出所有已注册的钩子。

    示例：
        python main.py list-hooks
    """
    registry = get_hook_registry()
    status = registry.get_status()
    
    console.print(f"\n[bold]Hook Registry Status[/bold]\n")
    console.print(f"[dim]Total hooks:[/dim] {status['total_hooks']}")
    console.print(f"[dim]Enabled:[/dim] {status['enabled_hooks']}")
    console.print(f"[dim]Disabled:[/dim] {status['disabled_hooks']}")
    console.print()
    
    console.print("[bold]Hooks:[/bold]\n")
    
    for hook_info in status.get("hooks", []):
        h_name = hook_info["name"]
        h_status = hook_info["status"]
        h_events = ", ".join(hook_info["events"][:3])  # 只显示前3个事件
        
        status_color = "[green]ready[/green]" if h_status == "ready" else f"[yellow]{h_status}[/yellow]"
        
        console.print(f"  • [bold]{h_name}[/bold] [{status_color}]")
        console.print(f"    Events: {h_events}")


@app.command("repl")
def repl() -> None:
    """
    启动交互式 REPL 模式。

    示例：
        python main.py repl
    """
    config = Config.from_env()
    config.verbose = True  # REPL 模式默认 verbose
    
    initialize_system(config)
    
    engine_config = AgentConfig(
        model=config.model,
        max_iterations=config.max_iterations,
        stream=True,
        verbose=config.verbose,
        system_prompt=DEFAULT_SYSTEM_PROMPT,
    )
    
    engine = QueryEngine(
        config=engine_config,
        console=console,
    )
    
    asyncio.run(_run_repl(engine, config))


@app.command("doctor")
def doctor() -> None:
    """
    运行诊断检查。

    示例：
        python main.py doctor
    """
    console.print(Panel(
        "[bold cyan]Claude Code Python - Doctor[/bold cyan]",
        border_style="cyan",
    ))
    
    issues = []
    
    # 检查 API key
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("API_KEY")
    if not api_key:
        issues.append("ANTHROPIC_API_KEY not set")
        console.print("[red]✗[/red] API key not configured")
    else:
        console.print(f"[green]✓[/green] API key configured (last 4: ...{api_key[-4:]})")
    
    # 检查 Python 版本
    if sys.version_info < (3, 9):
        issues.append("Python 3.9+ required")
        console.print(f"[red]✗[/red] Python {sys.version_info.major}.{sys.version_info.minor} (need 3.9+)")
    else:
        console.print(f"[green]✓[/green] Python {sys.version_info.major}.{sys.version_info.minor}")
    
    # 检查依赖
    try:
        import anthropic
        console.print("[green]✓[/green] anthropic SDK installed")
    except ImportError:
        issues.append("anthropic not installed")
        console.print("[red]✗[/red] anthropic SDK not installed")
    
    try:
        import tiktoken
        console.print("[green]✓[/green] tiktoken installed")
    except ImportError:
        issues.append("tiktoken not installed (token counting limited)")
        console.print("[yellow]⚠[/yellow] tiktoken not installed")
    
    # 初始化系统
    initialize_system(Config())
    
    # 检查工具注册
    registry = get_tool_registry()
    tool_count = len(registry.list_tools())
    console.print(f"[green]✓[/green] {tool_count} tools registered")
    
    # 检查钩子注册
    hook_registry = get_hook_registry()
    hook_status = hook_registry.get_status()
    console.print(f"[green]✓[/green] {hook_status['total_hooks']} hooks registered")
    
    # 总结
    console.print()
    if issues:
        console.print(Panel(
            f"[yellow]Found {len(issues)} issue(s):[/yellow]\n" +
            "\n".join(f"  - {issue}" for issue in issues),
            title="Issues Found",
            border_style="yellow",
        ))
    else:
        console.print(Panel(
            "[green]All checks passed![/green]",
            title="Doctor",
            border_style="green",
        ))


# ---------------------------------------------------------------------------
# 入口点
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
