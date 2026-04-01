"""
REPL - 交互式命令行界面

提供交互式的读取-执行-打印循环。
对应 Claude Code 源码: src/repl/*.ts
参考: Claude Code CLI 交互界面

核心功能：
1. 命令行提示符
2. 多行输入支持（检测缩进）
3. Ctrl+C / Ctrl+D 处理
4. 历史命令记录
5. 交互式输出（Markdown 渲染）
"""

from __future__ import annotations

import asyncio
import atexit
import os
import readline
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Any

from agent.query_engine import QueryEngine, AgentConfig, AgentState
from commands.base import CommandContext, CommandResult
from commands.registry import get_command_registry, register_builtin_commands
from hook.events import EventType, HookEvent, create_session_event
from hook.registry import get_hook_registry


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


class REPL:
    """
    交互式命令行解释器。
    对应 Claude Code 源码: src/repl/REPL.ts
    
    提供用户与 QueryEngine 的交互界面：
    1. 读取用户输入（支持多行）
    2. 调用 QueryEngine 处理
    3. 打印输出（Markdown 渲染）
    4. 循环直到用户退出
    
    使用 readline 提供：
    - 命令历史（上下箭头）
    - 行编辑（左右箭头）
    - 自动补全（Tab）
    - Ctrl+R 搜索历史
    
    示例：
        repl = REPL(query_engine)
        await repl.run()
    """

    def __init__(
        self,
        query_engine: QueryEngine,
        config: Optional[REPLConfig] = None,
    ) -> None:
        """
        初始化 REPL。
        
        Args:
            query_engine: QueryEngine 实例
            config: REPL 配置
        """
        self.engine = query_engine
        self.config = config or REPLConfig()
        self.hook_registry = get_hook_registry()
        
        # 初始化命令注册表
        self.cmd_registry = get_command_registry()
        register_builtin_commands()
        
        # 状态
        self._running: bool = False
        self._session_id: Optional[str] = None
        self._input_lines: List[str] = []
        self._multiline_depth: int = 0

    # =========================================================================
    # 主循环
    # =========================================================================

    async def run(self) -> None:
        """
        运行 REPL 主循环。
        
        这是异步主入口，会阻塞直到用户退出。
        """
        self._running = True
        
        # 设置 readline
        self._setup_readline()
        
        # 注册清理函数
        atexit.register(self._cleanup)
        
        # 发送会话开始事件
        await self._emit_session_event(EventType.SESSION_START)
        
        # 显示欢迎信息
        if not self.config.quiet:
            self._print_welcome()
        
        try:
            while self._running:
                try:
                    # 读取一行输入
                    line = await self._read_line()
                    
                    if line is None:  # EOF (Ctrl+D)
                        self._handle_eof()
                        break
                    
                    # 处理输入
                    await self._process_line(line)
                    
                except KeyboardInterrupt:
                    self._handle_interrupt()
                except EOFError:
                    self._handle_eof()
                    break
                except Exception as e:
                    self._handle_error(e)
        
        finally:
            # 发送会话结束事件
            await self._emit_session_event(EventType.SESSION_END)
            self._cleanup()

    async def run_single(self, message: str) -> str:
        """
        执行单次查询（不进入交互模式）。
        
        Args:
            message: 用户消息
            
        Returns:
            助手的最终回复
        """
        return await self.engine.run(message)

    # =========================================================================
    # 输入处理
    # =========================================================================

    async def _read_line(self) -> Optional[str]:
        """
        读取一行输入。
        
        支持多行输入：当用户输入以冒号或反斜杠结尾时，
        继续读取下一行。
        
        Returns:
            用户输入的行，或 None（EOF）
        """
        self._input_lines = []
        self._multiline_depth = 0
        
        while True:
            # 选择提示符
            if self._multiline_depth > 0:
                prompt = self.config.multiline_prompt
            else:
                prompt = self.config.prompt
            
            # 读取一行（非异步，使用同步 readline）
            try:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, input, prompt
                )
            except (EOFError, OSError):
                return None
            
            # 去掉末尾换行
            if line is not None:
                line = line.rstrip("\r\n")
            
            # 检查是否是多行继续
            if self._should_continue(line):
                self._input_lines.append(line.rstrip())
                self._multiline_depth += 1
                
                # 防止无限嵌套
                if self._multiline_depth >= self.config.max_multiline_depth:
                    break
                continue
            
            # 单行输入
            if self._input_lines:
                self._input_lines.append(line.rstrip() if line else "")
                return "\n".join(self._input_lines)
            
            return line

    def _should_continue(self, line: Optional[str]) -> bool:
        """
        检查是否应该继续读取多行输入。
        
        触发条件：
        - 行末是反斜杠 \\
        - 行末是冒号 :
        - 行末是开括号 ( [ {
        - 当前在多行块内（检测缩进）
        """
        if line is None:
            return False
        
        stripped = line.strip()
        
        # 显式标记
        if stripped.endswith("\\"):
            return True
        
        # 括号匹配
        if stripped.endswith(":") or stripped.endswith("{") or stripped.endswith("["):
            return True
        
        # 多行内继续（检测缩进）
        if self._multiline_depth > 0 and (stripped.startswith(" ") or stripped.startswith("\t")):
            return True
        
        return False

    async def _process_line(self, line: Optional[str]) -> None:
        """
        处理一行输入。
        
        Args:
            line: 用户输入的行
        """
        # 空行跳过
        if not line or not line.strip():
            return
        
        # 命令处理
        if line.startswith("/"):
            await self._handle_command(line)
            return
        
        # 发送到 QueryEngine
        if self.config.quiet:
            await self.engine.run(line)
        else:
            print()  # 空行分隔
            await self.engine.run(line)
            print()

    # =========================================================================
    # 命令处理
    # =========================================================================

    async def _handle_command(self, line: str) -> None:
        """处理命令（通过 CommandRegistry）"""
        # 解析命令名称和参数
        parts = line.split()
        cmd_name = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        # 查找命令
        cmd = self.cmd_registry.get(cmd_name.lstrip("/"))
        
        if cmd is None:
            print(f"Unknown command: {cmd_name}")
            print("Type /help for available commands")
            return
        
        # 构建命令上下文
        from cost_tracker import CostTracker
        cost_tracker = CostTracker() if hasattr(self, '_cost_tracker') else None
        
        context = CommandContext(
            session_id=self._session_id or "unknown",
            repl=self,
            engine=self.engine,
            hook_registry=self.hook_registry,
            cost_tracker=cost_tracker,
        )
        
        # 执行命令
        try:
            result = await cmd.execute(args, context)
            
            # 打印输出
            if result.output:
                print(result.output)
            
            # 如果命令返回错误
            if not result.success and result.error:
                print(f"Error: {result.error}")
        
        except Exception as e:
            print(f"Command failed: {type(e).__name__}: {e}")

    async def _cmd_quit(self, line: str) -> None:
        """退出命令"""
        print("Goodbye!")
        self._running = False



    # =========================================================================
    # 事件
    # =========================================================================

    async def _emit_command_event(self, command: str, line: str) -> None:
        """发送命令事件"""
        args = line.split()[1:] if len(line.split()) > 1 else []
        
        event = create_session_event(
            EventType.COMMAND_NEW if command == "new" else EventType.COMMAND_RESET,
            session_id=self._session_id,
        )
        
        await self.hook_registry.emit(event)

    async def _emit_session_event(self, event_type: EventType) -> None:
        """发送会话事件"""
        # 生成会话 ID
        if self._session_id is None:
            import uuid
            self._session_id = f"session_{uuid.uuid4().hex[:12]}"
        
        event = create_session_event(
            event_type,
            session_id=self._session_id,
        )
        
        await self.hook_registry.emit(event)

    # =========================================================================
    # readline 设置
    # =========================================================================

    def _setup_readline(self) -> None:
        """配置 readline"""
        # 历史文件
        if self.config.history_file:
            hist_file = os.path.expanduser(self.config.history_file)
        else:
            hist_file = os.path.expanduser("~/.claude_code_history")
        
        # 确保目录存在
        Path(hist_file).parent.mkdir(parents=True, exist_ok=True)
        
        # 加载历史
        if os.path.exists(hist_file):
            try:
                readline.read_history_file(hist_file)
                readline.set_history_length(self.config.history_size)
            except Exception:
                pass
        
        # 注册清理函数（保存历史）
        def save_history():
            try:
                readline.write_history_file(hist_file)
            except Exception:
                pass
        
        atexit.register(save_history)

    def _cleanup(self) -> None:
        """清理函数"""
        try:
            readline.write_history_file(os.path.expanduser("~/.claude_code_history"))
        except Exception:
            pass

    # =========================================================================
    # 信号处理
    # =========================================================================

    def _handle_interrupt(self) -> None:
        """处理 Ctrl+C"""
        if self.engine.is_running:
            print("\n^C")
            print("Interrupting...")
            self.engine.stop()
        else:
            print("\n^C")
            self._input_lines = []  # 取消当前输入

    def _handle_eof(self) -> None:
        """处理 EOF (Ctrl+D)"""
        print("\n^D")
        print("Goodbye!")
        self._running = False

    def _handle_error(self, error: Exception) -> None:
        """处理异常"""
        print(f"\nError: {type(error).__name__}: {error}")
        if self.config.quiet:
            traceback.print_exc()

    # =========================================================================
    # 输出
    # =========================================================================

    def _print_welcome(self) -> None:
        """打印欢迎信息"""
        print(self.config.welcome_message)

    def _default_welcome(self) -> str:
        """默认欢迎信息"""
        return f"""
=== Claude Code Python REPL ===
Type /help for commands, /quit to exit.

Current model: {self.engine.config.model}
Session: {self._session_id or 'new'}
"""

    # =========================================================================
    # 工具方法
    # =========================================================================

    def set_session_id(self, session_id: str) -> None:
        """设置会话 ID"""
        self._session_id = session_id

    def get_session_id(self) -> Optional[str]:
        """获取会话 ID"""
        return self._session_id

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running
