"""
CommandLoggerHook - 命令日志钩子

将所有命令事件记录到集中的审计文件中。
对应 Claude Code 源码: 内置钩子
参考: OpenClaw command-logger hook
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from hook.base import Hook, HookConfig, HookResult
from hook.events import EventType, HookEvent


class CommandLoggerHook(Hook):
    """
    命令日志钩子。
    
    将所有命令事件记录到 JSONL 审计日志文件。
    
    触发时机：
    - command:new - 执行 /new 命令
    - command:reset - 执行 /reset 命令
    - command:quit - 执行 /quit 命令
    - command:custom - 自定义命令
    - session:start - 会话开始
    - session:end - 会话结束
    
    输出：
    - `~/.openclaw/logs/commands.log` - JSONL 格式审计日志
    
    日志格式：
    {
        "timestamp": 1709337600.123,
        "event": "command:new",
        "session_id": "sess_abc123",
        "args": ["arg1", "arg2"],
        "duration_ms": 1500,
        "success": true
    }
    """

    name = "command-logger"
    description = "Log all command events to a centralized audit file"
    version = "1.0.0"

    def __init__(
        self,
        log_file: Optional[str] = None,
        log_dir: Optional[str] = None,
    ) -> None:
        """
        初始化命令日志钩子。
        
        Args:
            log_file: 日志文件名（默认 commands.log）
            log_dir: 日志目录（默认 ~/.openclaw/logs/）
        """
        super().__init__()
        
        # 确定日志路径
        if log_dir:
            self.log_dir = Path(log_dir)
        else:
            # 默认 ~/.openclaw/logs/
            from pathlib import Path
            home = Path.home()
            self.log_dir = home / ".openclaw" / "logs"
        
        self.log_file = self.log_dir / (log_file or "commands.log")
        
        self.config = HookConfig(
            enabled=True,
            async_execute=True,  # 异步执行，不阻塞命令
        )
        
        # 确保目录存在
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 设置日志器
        self._logger = logging.getLogger(f"hook.{self.name}")

    def get_events(self) -> List[EventType]:
        return [
            EventType.COMMAND_NEW,
            EventType.COMMAND_RESET,
            EventType.COMMAND_QUIT,
            EventType.COMMAND_CUSTOM,
            EventType.SESSION_START,
            EventType.SESSION_END,
        ]

    async def handle(self, event: HookEvent) -> HookResult:
        """处理事件，记录到日志"""
        try:
            # 构建日志条目
            log_entry = self._build_log_entry(event)
            
            # 写入 JSONL 文件
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            
            return HookResult.ok(output={"logged": str(self.log_file)})
        
        except Exception as e:
            return HookResult.err(f"CommandLoggerHook failed: {e}")

    def _build_log_entry(self, event: HookEvent) -> Dict[str, Any]:
        """从事件构建日志条目"""
        entry = {
            "timestamp": event.timestamp,
            "datetime": event.datetime.isoformat(),
            "event": event.type.value,
            "source": event.source,
        }
        
        # 根据事件类型添加特定数据
        data = event.data
        
        if event.type in (
            EventType.COMMAND_NEW,
            EventType.COMMAND_RESET,
            EventType.COMMAND_QUIT,
            EventType.COMMAND_CUSTOM,
        ):
            entry["command"] = data.get("command", "")
            entry["args"] = data.get("args", [])
        
        elif event.type in (EventType.SESSION_START, EventType.SESSION_END):
            entry["session_id"] = data.get("session_id", "")
            entry["user_id"] = data.get("user_id")
            entry["agent_id"] = data.get("agent_id")
            
            if event.type == EventType.SESSION_END:
                entry["duration_seconds"] = data.get("duration_seconds", 0)
                entry["message_count"] = data.get("message_count", 0)
        
        return entry

    def get_recent_logs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取最近的日志条目。
        
        Args:
            limit: 返回数量限制
            
        Returns:
            日志条目列表
        """
        logs = []
        
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            # 逆序读取最后 N 行
            for line in lines[-limit:]:
                line = line.strip()
                if line:
                    try:
                        logs.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        
        except FileNotFoundError:
            pass
        
        return logs

    def query_logs(
        self,
        event_type: Optional[str] = None,
        session_id: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        查询日志。
        
        Args:
            event_type: 按事件类型过滤
            session_id: 按会话 ID 过滤
            start_time: 起始时间戳
            end_time: 结束时间戳
            limit: 返回数量限制
            
        Returns:
            匹配的日志条目列表
        """
        logs = []
        
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    
                    # 应用过滤器
                    if event_type and entry.get("event") != event_type:
                        continue
                    if session_id and entry.get("session_id") != session_id:
                        continue
                    if start_time and entry.get("timestamp", 0) < start_time:
                        continue
                    if end_time and entry.get("timestamp", float("inf")) > end_time:
                        continue
                    
                    logs.append(entry)
                    
                    if len(logs) >= limit:
                        break
        
        except FileNotFoundError:
            pass
        
        return logs
