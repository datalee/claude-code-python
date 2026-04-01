"""
SessionMemoryHook - 会话记忆钩子

在 /new 命令时自动保存当前会话上下文到记忆。
对应 Claude Code 源码: 内置钩子
参考: OpenClaw session-memory hook
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from hook.base import Hook, HookConfig, HookResult
from hook.events import EventType, HookEvent


class SessionMemoryHook(Hook):
    """
    会话记忆钩子。
    
    在执行 /new 命令时，保存当前会话的上下文到记忆文件。
    这样下次新会话开始时可以加载之前的上下文。
    
    触发时机：
    - command:new - 执行 /new 命令时
    - session:end - 会话结束时
    
    输出：
    - `memory/YYYY-MM-DD.md` - 每日日记文件
    """

    name = "session-memory"
    description = "Save session context to memory when /new command is issued"
    version = "1.0.0"

    def __init__(
        self,
        workspace_path: Optional[str] = None,
        memory_dir: str = "memory",
    ) -> None:
        """
        初始化会话记忆钩子。
        
        Args:
            workspace_path: 工作空间路径
            memory_dir: 记忆目录名
        """
        super().__init__()
        self.workspace_path = Path(workspace_path) if workspace_path else Path.cwd()
        self.memory_dir = self.workspace_path / memory_dir
        self.config = HookConfig(
            enabled=True,
            async_execute=True,
        )

    def get_events(self) -> List[EventType]:
        return [
            EventType.COMMAND_NEW,
            EventType.SESSION_END,
        ]

    async def handle(self, event: HookEvent) -> HookResult:
        """处理事件，保存会话上下文"""
        try:
            if event.type == EventType.COMMAND_NEW:
                return await self._handle_new_command(event)
            elif event.type == EventType.SESSION_END:
                return await self._handle_session_end(event)
            
            return HookResult.err(f"Unexpected event type: {event.type}")
        
        except Exception as e:
            return HookResult.err(f"SessionMemoryHook failed: {e}")

    async def _handle_new_command(self, event: HookEvent) -> HookResult:
        """处理 /new 命令，保存旧会话"""
        session_id = event.get("session_id")
        
        # 确保目录存在
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成日记文件路径
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        date_file = self.memory_dir / f"{date_str}.md"
        
        # 获取当前会话上下文（如果有）
        context_data = event.get("context") or {}
        summary = context_data.get("summary", "")
        decisions = context_data.get("decisions", [])
        preferences = context_data.get("preferences", [])
        
        # 写入日记
        lines = [
            f"\n## 会话结束: {session_id or 'unknown'}",
            f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**触发**: /new 命令",
            "",
        ]
        
        if summary:
            lines.append(f"**摘要**: {summary}")
        
        if decisions:
            lines.append("")
            lines.append("**决策**:")
            for d in decisions:
                lines.append(f"- {d}")
        
        if preferences:
            lines.append("")
            lines.append("**偏好**:")
            for p in preferences:
                lines.append(f"- {p}")
        
        content = "\n".join(lines)
        
        with open(date_file, "a", encoding="utf-8") as f:
            f.write(content)
        
        return HookResult.ok(output={"saved_to": str(date_file)})

    async def _handle_session_end(self, event: HookEvent) -> HookResult:
        """处理会话结束事件"""
        session_id = event.get("session_id")
        duration = event.get("duration_seconds", 0)
        message_count = event.get("message_count", 0)
        
        # 确保目录存在
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成日记
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        date_file = self.memory_dir / f"{date_str}.md"
        
        lines = [
            f"\n## 会话结束: {session_id or 'unknown'}",
            f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**持续**: {duration:.1f} 秒",
            f"**消息数**: {message_count}",
            "",
        ]
        
        content = "\n".join(lines)
        
        with open(date_file, "a", encoding="utf-8") as f:
            f.write(content)
        
        return HookResult.ok(output={"saved_to": str(date_file)})
