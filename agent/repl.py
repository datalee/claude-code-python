"""
REPL - 交互式命令行界面 (改进版)

使用 prompt_toolkit 实现：
- 命令补全（Tab）
- 语法高亮
- 更好的终端美化
- 多行输入支持
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Callable, List, Optional, Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from agent.query_engine import QueryEngine, AgentConfig, AgentState


# =============================================================================
# 样式和主题
# =============================================================================

# 自定义样式
REPL_STYLE = Style.from_dict({
    "prompt": "#00d7ff bold",           # 青色提示符
    "user-input": "#ffffff",            # 用户输入
    "assistant": "#98fb98",             # 绿色助手输出
    "error": "#ff6b6b bold",            # 红色错误
    "warning": "#ffd700",                # 黄色警告
    "info": "#00bfff",                  # 蓝色信息
    "tool": "#ff79c6",                  # 粉色工具名
    "command": "#8be9fd",               # 淡蓝色命令
})





# =============================================================================
# 命令补全器
# =============================================================================

class REPLCompleter(Completer):
    """REPL 命令补全器"""
    
    def __init__(self, commands: List[str]):
        self.commands = sorted(commands)
        # 添加常见操作
        self.extras = [
            "read ", "edit ", "glob ", "bash ", "search ",
            "weather ", "web_search ", "web_fetch ",
        ]
    
    def get_completions(self, document, complete_event):
        text = document.text.lower()
        
        # 补全 / 命令
        if text.startswith("/"):
            for cmd in self.commands:
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text))
        
        # 补全常见操作
        elif " " in text:
            prefix = text.split()[-1]
            for extra in self.extras:
                if extra.startswith(prefix):
                    yield Completion(extra, start_position=-len(prefix))
        
        # 补全普通单词
        else:
            for cmd in self.commands:
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text))


# =============================================================================
# REPL 配置
# =============================================================================

class REPLConfig:
    """REPL 配置"""
    
    def __init__(
        self,
        prompt: str = ">>> ",
        multiline_prompt: str = "... ",
        history_file: Optional[str] = None,
        history_size: int = 1000,
        max_multiline_depth: int = 3,
        quiet: bool = False,
        welcome_message: Optional[str] = None,
    ) -> None:
        self.prompt = prompt
        self.multiline_prompt = multiline_prompt
        self.history_file = history_file
        self.history_size = history_size
        self.max_multiline_depth = max_multiline_depth
        self.quiet = quiet
        self.welcome_message = welcome_message or self._default_welcome()
    
    def _default_welcome(self) -> str:
        return """[bold cyan]Claude Code Python[/bold cyan] - REPL Mode

[dim]Type your request or [/dim][yellow]/help[/yellow][dim] for commands[/dim]"""


# =============================================================================
# 改进版 REPL
# =============================================================================

class REPL:
    """
    改进版 REPL，使用 prompt_toolkit 实现更好的用户体验。
    """
    
    def __init__(
        self,
        query_engine: QueryEngine,
        config: Optional[REPLConfig] = None,
        console: Optional[Console] = None,
    ) -> None:
        self.engine = query_engine
        self.config = config or REPLConfig()
        self.console = console or Console()
        self.cmd_registry = self.engine.cmd_registry if hasattr(self.engine, 'cmd_registry') else None
        
        # 创建补全器
        self._setup_completer()
        
        # 创建 session（带历史记录）
        # 注意：PromptSession 在某些环境下可能不可用（如管道输入）
        self.session = None
        self._use_prompt_toolkit = True
        
        try:
            history = None
            if self.config.history_file:
                history = FileHistory(os.path.expanduser(self.config.history_file))
            
            self.session = PromptSession(
                history=history,
                completer=self.completer,
                style=REPL_STYLE,
            )
        except Exception:
            # prompt_toolkit 在非交互模式下不可用
            self._use_prompt_toolkit = False
            self.session = None
        
        self._is_multiline = False
    
    def _setup_completer(self):
        """设置命令补全器"""
        commands = [
            "/help", "/clear", "/exit", "/quit", "/model", "/tools",
            "/status", "/tasks", "/skills", "/cost", "/compact",
            "/memory", "/config", "/context", "/diff", "/doctor",
        ]
        
        # 添加 /skills 列出的具体 skill
        try:
            from skill import get_skill_loader
            loader = get_skill_loader()
            for s in loader.list_skills():
                commands.append(f"/{s.slug}")
        except:
            pass
        
        self.completer = REPLCompleter(commands)
    
    async def run(self) -> None:
        """
        运行 REPL 主循环。
        """
        # 显示欢迎信息
        if not self.config.quiet:
            self.console.print(Panel(
                "[bold cyan]Claude Code Python[/bold cyan] - Interactive Mode",
                border_style="cyan",
                subtitle="Type /help for commands, Ctrl+C to interrupt",
            ))
        
        try:
            while True:
                try:
                    # 获取用户输入
                    if self.session and self._use_prompt_toolkit:
                        # 使用 prompt_toolkit（交互模式）
                        user_input = await self.session.prompt()
                    else:
                        # 使用标准 input（管道模式或非交互模式）
                        user_input = input(">>> ")
                    
                    if not user_input.strip():
                        continue
                    
                    # 处理命令
                    if user_input.startswith("/"):
                        await self._handle_command(user_input)
                    else:
                        # 发送给引擎处理
                        await self._handle_query(user_input)
                
                except KeyboardInterrupt:
                    self.console.print("\n[yellow]Interrupted. Press Ctrl+D to exit.[/yellow]")
                    self._is_multiline = False
                    continue
                
                except EOFError:
                    break
        
        except ExitREPL:
            pass
        
        self.console.print("\n[dim]Goodbye![/dim]")
    
    async def _handle_command(self, command: str) -> None:
        """处理 / 命令"""
        parts = command.split()
        cmd_name = parts[0].lstrip("/")
        args = parts[1:] if len(parts) > 1 else []
        
        # 内部命令处理
        if cmd_name in ("exit", "quit"):
            raise ExitREPL()
        
        elif cmd_name == "help":
            self._print_help()
        
        elif cmd_name == "clear":
            self.console.clear()
        
        else:
            self.console.print(f"[yellow]Unknown command: {command}[/yellow]")
            self.console.print("Type /help for available commands.")
    
    async def _handle_query(self, query: str) -> None:
        """处理用户查询"""
        # 注意：engine.run() 内部已经打印了响应，所以这里不再打印
        try:
            await self.engine.run(query)
        except Exception as e:
            self.console.print(f"[red bold]Error: {e}[/red bold]")
    
    def _print_help(self) -> None:
        """打印帮助信息"""
        table = Table(title="Available Commands", show_header=True)
        table.add_column("Command", style="cyan")
        table.add_column("Description", style="white")
        
        commands = [
            ("/help", "Show this help"),
            ("/clear", "Clear the screen"),
            ("/exit, /quit", "Exit REPL"),
            ("/model", "Show current model"),
            ("/tools", "List available tools"),
            ("/status", "Show status"),
            ("/tasks", "Show tasks"),
            ("/skills", "List available skills"),
            ("/cost", "Show API cost"),
            ("/compact", "Compact context"),
            ("/memory", "Memory operations"),
            ("/config", "Show configuration"),
            ("/context", "Show context info"),
            ("/diff", "Git diff"),
            ("/doctor", "Run diagnostics"),
        ]
        
        for cmd, desc in commands:
            table.add_row(cmd, desc)
        
        self.console.print(table)
    
    def _print_response(self, response: str) -> None:
        """打印响应，美化格式"""
        if not response.strip():
            return
        
        # 打印分隔线
        self.console.print()
        
        # 尝试渲染为 Markdown
        try:
            md = Markdown(response)
            self.console.print(md)
        except:
            self.console.print(response)
        
        self.console.print()


class ExitREPL(Exception):
    """退出 REPL 的异常"""
    pass


# 保留旧的兼容接口
class OldREPL(REPL):
    """保留旧版 REPL 以兼容"""
    pass


__all__ = ["REPL", "REPLConfig", "ExitREPL"]
