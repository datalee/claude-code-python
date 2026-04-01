"""
Command 基类 - 命令抽象基类

定义所有命令的接口。
对应 Claude Code 源码: src/commands/*.ts
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CommandResult:
    """
    命令执行结果。
    
    Attributes:
        success: 是否成功
        output: 命令输出（要打印的内容）
        error: 错误信息（失败时）
        data: 附加数据（供其他组件使用）
    """
    success: bool
    output: str = ""
    error: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, output: str = "", **kwargs) -> "CommandResult":
        """成功结果"""
        return cls(success=True, output=output, data=kwargs)

    @classmethod
    def err(cls, error: str, output: str = "") -> "CommandResult":
        """错误结果"""
        return cls(success=False, error=error, output=output)


class Command(ABC):
    """
    命令抽象基类。
    对应 Claude Code 源码: src/commands/Command.ts
    
    所有命令必须继承此类并实现：
    1. name - 命令名称（如 "new", "reset"）
    2. description - 命令描述（用于 /help）
    3. execute() - 执行逻辑
    
    可选覆盖：
    4. aliases - 命令别名列表
    5. usage - 使用说明
    6. patterns - 匹配模式（支持正则）
    
    示例：
        class NewCommand(Command):
            name = "new"
            description = "Start a new session"
            aliases = ["n"]
            usage = "/new [session_name]"
            
            async def execute(self, args: List[str], context: CommandContext) -> CommandResult:
                # ...
                return CommandResult.ok("New session started")
    """

    # -------------------------------------------------------------------------
    # 必须实现的属性
    # -------------------------------------------------------------------------

    name: str = ""
    """命令名称（不带斜杠），如 "new", "reset" """

    description: str = ""
    """命令描述，用于 /help 显示 """

    # -------------------------------------------------------------------------
    # 可选的属性
    # -------------------------------------------------------------------------

    aliases: List[str] = field(default_factory=list)
    """命令别名列表，如 ["n", "restart"] """

    usage: str = ""
    """使用说明，如 "/new [session_name]\n  Start a new session.\" """

    patterns: List[str] = field(default_factory=list)
    """正则匹配模式，如 [r"^/new$", r"^/n$"] """

    # -------------------------------------------------------------------------
    # 执行方法
    # -------------------------------------------------------------------------

    @abstractmethod
    async def execute(self, args: List[str], context: "CommandContext") -> CommandResult:
        """
        执行命令。
        
        Args:
            args: 命令参数（分割后的列表，不包含命令本身）
            context: 命令执行上下文
            
        Returns:
            CommandResult: 命令执行结果
        """
        ...

    # -------------------------------------------------------------------------
    # 工具方法
    # -------------------------------------------------------------------------

    def matches(self, input_str: str) -> bool:
        """
        检查输入是否匹配此命令。
        
        默认实现：检查 input_str 是否等于 name 或 any(aliases)
        
        Args:
            input_str: 用户输入（已去除首尾空白）
            
        Returns:
            True 如果匹配
        """
        cmd = input_str.strip().lstrip("/").split()[0].lower()
        return cmd == self.name.lower() or cmd in [a.lower() for a in self.aliases]

    def get_full_name(self) -> str:
        """返回完整的命令名称（带斜杠）"""
        return f"/{self.name}"

    def get_all_names(self) -> List[str]:
        """返回所有名称（主名称 + 别名）"""
        names = [self.get_full_name()]
        names.extend(f"/{alias}" for alias in self.aliases)
        return names

    def format_help(self) -> str:
        """格式化帮助信息"""
        lines = []
        for name in self.get_all_names():
            lines.append(f"  {name}")
            if self.usage:
                for line in self.usage.split("\n")[1:]:
                    lines.append(f"      {line}")
        lines.append(f"      {self.description}")
        return "\n".join(lines)


@dataclass
class CommandContext:
    """
    命令执行上下文。
    传递给每个命令的 execute() 方法。
    
    Attributes:
        session_id: 当前会话 ID
        user_id: 用户 ID
        agent_id: Agent ID
        repl: REPL 实例（可用于访问 engine 等）
        engine: QueryEngine 实例
        hook_registry: 钩子注册表
        cost_tracker: 成本追踪器
    """
    session_id: str
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    repl: Any = None
    engine: Any = None
    hook_registry: Any = None
    cost_tracker: Any = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """从 extra 获取值"""
        return self.extra.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置 extra 值"""
        self.extra[key] = value
