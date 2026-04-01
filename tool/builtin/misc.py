"""
Misc Tools - 杂项工具

包括：ScheduleCronTool, SleepTool, EnterPlanModeTool, ExitPlanModeTool
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from tool.base import Tool, ToolResult, Permission, PermissionScope, PermissionMode


class SleepTool(Tool):
    """
    Sleep for a specified duration.

    Useful for waiting for external processes or rate limiting.

    示例：
        sleep(seconds=5)
    """

    name = "sleep"
    description = "Sleep for a specified number of seconds."
    permission = Permission(mode=PermissionMode.AUTOMATIC, scope=PermissionScope.READ)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "seconds": {
                    "type": "number",
                    "description": "Number of seconds to sleep",
                    "minimum": 0,
                    "maximum": 3600,
                },
            },
            "required": ["seconds"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        seconds = input_data["seconds"]

        try:
            await asyncio.sleep(seconds)
            return ToolResult.ok(
                content=f"Slept for {seconds} seconds",
                metadata={"slept_seconds": seconds}
            )
        except Exception as e:
            return ToolResult.err(f"Sleep error: {e}")


class EnterPlanModeTool(Tool):
    """
    Enter plan mode.

    In plan mode, the agent thinks and plans but does not execute any tools.
    Useful for:
    - Breaking down complex tasks
    - Architecture planning
    - Code review planning

    示例：
        enter_plan_mode(reason="Plan the refactoring approach")
    """

    name = "enter_plan_mode"
    description = "Enter plan mode to think and plan without executing tools."
    permission = Permission(mode=PermissionMode.AUTOMATIC, scope=PermissionScope.READ)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why are you entering plan mode?",
                },
            },
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        reason = input_data.get("reason", "Planning")
        
        # Note: In a full implementation, this would set a flag on the agent
        # that prevents tool execution. For now, we just acknowledge the request.
        
        return ToolResult.ok(
            content=f"Entered plan mode: {reason}",
            metadata={"reason": reason, "plan_mode": True}
        )


class ExitPlanModeTool(Tool):
    """
    Exit plan mode and resume normal operation.

    示例：
        exit_plan_mode()
    """

    name = "exit_plan_mode"
    description = "Exit plan mode and resume normal tool execution."
    permission = Permission(mode=PermissionMode.AUTOMATIC, scope=PermissionScope.READ)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        return ToolResult.ok(
            content="Exited plan mode",
            metadata={"plan_mode": False}
        )


class ScheduleCronTool(Tool):
    """
    Schedule a task to run later (cron-like).

    Schedules a task for future execution. Note: This requires a running
    scheduler process to execute the scheduled tasks.

    示例：
        schedule_cron(
            task="Run tests",
            delay_seconds=3600,
            repeat=false
        )
    """

    name = "schedule_cron"
    description = "Schedule a task to run at a future time."
    permission = Permission(mode=PermissionMode.ASK, scope=PermissionScope.WRITE)

    def __init__(self):
        super().__init__()
        self._scheduled_tasks: Dict[str, Any] = {}

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Description of the task to run",
                },
                "delay_seconds": {
                    "type": "number",
                    "description": "Delay in seconds before running the task",
                    "minimum": 1,
                },
                "repeat": {
                    "type": "boolean",
                    "description": "Repeat the task",
                    "default": False,
                },
                "interval_seconds": {
                    "type": "number",
                    "description": "Repeat interval (if repeat=true)",
                    "minimum": 60,
                },
                "task_id": {
                    "type": "string",
                    "description": "Custom ID for the scheduled task",
                },
            },
            "required": ["task", "delay_seconds"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        task = input_data["task"]
        delay = input_data["delay_seconds"]
        repeat = input_data.get("repeat", False)
        interval = input_data.get("interval_seconds")
        task_id = input_data.get("task_id") or f"task_{len(self._scheduled_tasks)}"

        try:
            # 计算执行时间
            scheduled_time = datetime.now() + timedelta(seconds=delay)

            # 创建调度记录
            self._scheduled_tasks[task_id] = {
                "task": task,
                "delay_seconds": delay,
                "repeat": repeat,
                "interval_seconds": interval,
                "scheduled_time": scheduled_time.isoformat(),
                "status": "scheduled",
            }

            # 如果非重复，立即调度执行
            if not repeat:
                asyncio.create_task(self._execute_delayed(task, delay, task_id))
            else:
                asyncio.create_task(self._execute_repeated(task, interval or delay, task_id))

            return ToolResult.ok(
                content=f"Scheduled task '{task_id}' for {scheduled_time.isoformat()}",
                metadata={
                    "task_id": task_id,
                    "scheduled_time": scheduled_time.isoformat(),
                    "repeat": repeat,
                }
            )

        except Exception as e:
            return ToolResult.err(f"Schedule error: {e}")

    async def _execute_delayed(self, task: str, delay: float, task_id: str) -> None:
        """延迟执行"""
        await asyncio.sleep(delay)
        # 在实际实现中，这里会触发工具执行或发送通知
        if task_id in self._scheduled_tasks:
            self._scheduled_tasks[task_id]["status"] = "completed"

    async def _execute_repeated(self, task: str, interval: float, task_id: str) -> None:
        """重复执行"""
        while task_id in self._scheduled_tasks:
            await asyncio.sleep(interval)
            if task_id in self._scheduled_tasks:
                if self._scheduled_tasks[task_id]["status"] == "cancelled":
                    break
                # 执行任务
                await asyncio.create_task(self._execute_delayed(task, 0, task_id))


class CancelScheduleTool(Tool):
    """
    Cancel a scheduled task.

    示例：
        cancel_schedule(task_id="task_123")
    """

    name = "cancel_schedule"
    description = "Cancel a previously scheduled task."
    permission = Permission(mode=PermissionMode.ASK, scope=PermissionScope.WRITE)

    def __init__(self):
        super().__init__()
        self._scheduled_tasks: Dict[str, Any] = {}

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "ID of the task to cancel",
                },
            },
            "required": ["task_id"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        task_id = input_data["task_id"]

        if task_id not in self._scheduled_tasks:
            return ToolResult.err(f"Task not found: {task_id}")

        self._scheduled_tasks[task_id]["status"] = "cancelled"

        return ToolResult.ok(
            content=f"Cancelled task: {task_id}",
            metadata={"task_id": task_id}
        )


class ReadClipboardTool(Tool):
    """
    Read text from the system clipboard.

    示例：
        read_clipboard()
    """

    name = "read_clipboard"
    description = "Read text from the system clipboard."
    permission = Permission(mode=PermissionMode.ASK, scope=PermissionScope.READ)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        try:
            # 使用 tkinter（跨平台）
            import tkinter
            root = tkinter.Tk()
            root.withdraw()  # 隐藏窗口
            text = root.clipboard_get()
            root.destroy()
            
            return ToolResult.ok(
                content=text[:500] + "..." if len(text) > 500 else text,
                metadata={"length": len(text)}
            )
        except ImportError:
            return ToolResult.err("tkinter not available")
        except Exception as e:
            return ToolResult.err(f"Clipboard read error: {e}")


class WriteClipboardTool(Tool):
    """
    Write text to the system clipboard.

    示例：
        write_clipboard(text="Hello, world!")
    """

    name = "write_clipboard"
    description = "Write text to the system clipboard."
    permission = Permission(mode=PermissionMode.ASK, scope=PermissionScope.WRITE)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to copy to clipboard",
                },
            },
            "required": ["text"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        text = input_data["text"]

        try:
            import tkinter
            root = tkinter.Tk()
            root.withdraw()
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()
            root.destroy()
            
            return ToolResult.ok(
                content=f"Copied {len(text)} characters to clipboard",
                metadata={"length": len(text)}
            )
        except ImportError:
            return ToolResult.err("tkinter not available")
        except Exception as e:
            return ToolResult.err(f"Clipboard write error: {e}")
