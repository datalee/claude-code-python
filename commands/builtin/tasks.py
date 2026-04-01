"""
TasksCommand - 任务管理命令

对应 Claude Code 源码: src/commands/tasks/

功能：
- 创建任务
- 列出任务
- 更新任务状态
- 显示任务详情
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from commands.base import Command, CommandContext, CommandResult


@dataclass
class Task:
    """任务"""
    id: str
    title: str
    description: str = ""
    status: str = "pending"  # pending, in_progress, done
    priority: str = "medium"  # low, medium, high
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    due_at: Optional[float] = None


class TasksCommand(Command):
    """任务管理"""

    name = "tasks"
    description = "Manage tasks"
    aliases = ["task"]
    usage = """/tasks
    Manage tasks.

Commands:
  /tasks list         - List all tasks
  /tasks create <title> - Create new task
  /tasks show <id>    - Show task details
  /tasks done <id>    - Mark task as done
  /tasks delete <id> - Delete a task
  /tasks clear        - Clear completed tasks"""

    def __init__(self) -> None:
        self._tasks: Dict[str, Task] = {}
        self._next_id = 1

    async def execute(self, args: List[str], context: CommandContext) -> CommandResult:
        """执行 tasks 命令"""
        try:
            if not args:
                return CommandResult.ok(self._list_tasks())
            
            subcmd = args[0].lower()
            
            if subcmd == "list":
                return CommandResult.ok(self._list_tasks())
            
            elif subcmd == "create":
                if len(args) < 2:
                    return CommandResult.err("Usage: /tasks create <title>")
                return CommandResult.ok(self._create_task(" ".join(args[1:])))
            
            elif subcmd == "show":
                if len(args) < 2:
                    return CommandResult.err("Usage: /tasks show <id>")
                return CommandResult.ok(self._show_task(args[1]))
            
            elif subcmd in ("done", "complete"):
                if len(args) < 2:
                    return CommandResult.err("Usage: /tasks done <id>")
                return CommandResult.ok(self._set_done(args[1]))
            
            elif subcmd in ("delete", "remove", "rm"):
                if len(args) < 2:
                    return CommandResult.err("Usage: /tasks delete <id>")
                return CommandResult.ok(self._delete_task(args[1]))
            
            elif subcmd == "clear":
                return CommandResult.ok(self._clear_done())
            
            else:
                return CommandResult.err(f"Unknown subcommand: {subcmd}")
        
        except Exception as e:
            return CommandResult.err(f"Tasks error: {e}")

    def _list_tasks(self) -> str:
        """列出任务"""
        if not self._tasks:
            return "\nNo tasks. Create one with /tasks create <title>\n"
        
        lines = ["\n=== Tasks ===\n"]
        
        # 按状态分组
        pending = []
        in_progress = []
        done = []
        
        for task in self._tasks.values():
            if task.status == "pending":
                pending.append(task)
            elif task.status == "in_progress":
                in_progress.append(task)
            else:
                done.append(task)
        
        def format_task(t: Task) -> str:
            checkbox = "[x]" if t.status == "done" else "[ ]"
            return f"  {checkbox} {t.id}: {t.title}"
        
        if pending:
            lines.append("Pending:")
            lines.extend(format_task(t) for t in pending)
            lines.append("")
        
        if in_progress:
            lines.append("In Progress:")
            lines.extend(format_task(t) for t in in_progress)
            lines.append("")
        
        if done:
            lines.append("Done:")
            lines.extend(format_task(t) for t in done)
            lines.append("")
        
        lines.append("Use /tasks show <id> for details")
        lines.append("")
        return "\n".join(lines)

    def _create_task(self, title: str) -> str:
        """创建任务"""
        task_id = f"#{self._next_id}"
        self._next_id += 1
        
        task = Task(id=task_id, title=title)
        self._tasks[task_id] = task
        
        return f"\nTask created: {task_id}\n"

    def _show_task(self, task_id: str) -> str:
        """显示任务详情"""
        if task_id not in self._tasks:
            return f"\nTask not found: {task_id}\n"
        
        task = self._tasks[task_id]
        lines = [f"\n=== Task {task.id} ===\n"]
        lines.append(f"  Title: {task.title}")
        lines.append(f"  Status: {task.status}")
        lines.append(f"  Priority: {task.priority}")
        
        if task.description:
            lines.append(f"  Description: {task.description}")
        
        created = time.strftime("%Y-%m-%d %H:%M", time.localtime(task.created_at))
        lines.append(f"  Created: {created}")
        
        if task.due_at:
            due = time.strftime("%Y-%m-%d %H:%M", time.localtime(task.due_at))
            lines.append(f"  Due: {due}")
        
        lines.append("")
        return "\n".join(lines)

    def _set_done(self, task_id: str) -> str:
        """标记完成"""
        if task_id not in self._tasks:
            return f"\nTask not found: {task_id}\n"
        
        self._tasks[task_id].status = "done"
        self._tasks[task_id].updated_at = time.time()
        
        return f"\nTask {task_id} marked as done.\n"

    def _delete_task(self, task_id: str) -> str:
        """删除任务"""
        if task_id not in self._tasks:
            return f"\nTask not found: {task_id}\n"
        
        del self._tasks[task_id]
        return f"\nTask {task_id} deleted.\n"

    def _clear_done(self) -> str:
        """清除已完成任务"""
        to_delete = [tid for tid, t in self._tasks.items() if t.status == "done"]
        for tid in to_delete:
            del self._tasks[tid]
        
        return f"\nCleared {len(to_delete)} completed tasks.\n"
