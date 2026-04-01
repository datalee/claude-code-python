"""
Task Tools - 任务管理工具

创建、更新、列出任务。
对应 Claude Code 内置工具: TaskCreateTool, TaskUpdateTool, TaskListTool
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from tool.base import Tool, ToolResult, Permission, PermissionScope, PermissionMode


class TaskPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """任务数据结构"""
    id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    due_at: Optional[float] = None
    assignee: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "due_at": self.due_at,
            "assignee": self.assignee,
            "tags": self.tags,
            "metadata": self.metadata,
        }


class TaskStore:
    """
    任务存储（内存中）。
    
    在实际应用中可以使用数据库或文件系统。
    """
    
    def __init__(self):
        self._tasks: Dict[str, Task] = {}
    
    def create(self, title: str, description: str = "", **kwargs) -> Task:
        task = Task(
            id=str(uuid.uuid4())[:8],
            title=title,
            description=description,
            **kwargs
        )
        self._tasks[task.id] = task
        return task
    
    def get(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)
    
    def update(self, task_id: str, **updates) -> Optional[Task]:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        
        for key, value in updates.items():
            if hasattr(task, key):
                setattr(task, key, value)
        task.updated_at = time.time()
        return task
    
    def delete(self, task_id: str) -> bool:
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False
    
    def list(self, status: Optional[TaskStatus] = None, **filters) -> List[Task]:
        tasks = list(self._tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        for key, value in filters.items():
            tasks = [t for t in tasks if getattr(t, key, None) == value]
        
        # 按创建时间排序（新的在前）
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks
    
    def count(self, status: Optional[TaskStatus] = None) -> int:
        if status:
            return len([t for t in self._tasks.values() if t.status == status])
        return len(self._tasks)


# 全局任务存储
_task_store = TaskStore()


class TaskCreateTool(Tool):
    """
    Create a new task.

    示例：
        task_create(
            title="Fix login bug",
            description="Users cannot login with special characters",
            priority="high",
            tags=["bug", "urgent"]
        )
    """

    name = "task_create"
    description = "Create a new task with title, description, and metadata."
    permission = Permission(mode=PermissionMode.AUTOMATIC, scope=PermissionScope.WRITE)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Task title (required)",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed task description",
                    "default": "",
                },
                "priority": {
                    "type": "string",
                    "description": "Priority: low, medium, high",
                    "enum": ["low", "medium", "high"],
                    "default": "medium",
                },
                "due_at": {
                    "type": "string",
                    "description": "Due date (ISO 8601 format)",
                },
                "assignee": {
                    "type": "string",
                    "description": "Assignee name or ID",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Task tags",
                },
            },
            "required": ["title"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        title = input_data["title"]
        description = input_data.get("description", "")
        priority = input_data.get("priority", "medium")
        tags = input_data.get("tags", [])

        # 解析优先级
        try:
            priority_enum = TaskPriority(priority.lower())
        except ValueError:
            priority_enum = TaskPriority.MEDIUM

        # 解析截止时间
        due_at = None
        if "due_at" in input_data:
            try:
                due_at = datetime.fromisoformat(input_data["due_at"]).timestamp()
            except Exception:
                pass

        try:
            task = _task_store.create(
                title=title,
                description=description,
                priority=priority_enum,
                due_at=due_at,
                tags=tags,
                assignee=input_data.get("assignee"),
            )

            return ToolResult.ok(
                content=f"Task created: {task.id}",
                metadata=task.to_dict()
            )

        except Exception as e:
            return ToolResult.err(f"Failed to create task: {e}")


class TaskUpdateTool(Tool):
    """
    Update an existing task.

    示例：
        task_update(
            task_id="abc123",
            status="done"
        )
    """

    name = "task_update"
    description = "Update an existing task's properties."
    permission = Permission(mode=PermissionMode.AUTOMATIC, scope=PermissionScope.WRITE)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Task ID to update",
                },
                "title": {
                    "type": "string",
                    "description": "New task title",
                },
                "description": {
                    "type": "string",
                    "description": "New task description",
                },
                "status": {
                    "type": "string",
                    "description": "New status: pending, in_progress, done, cancelled",
                    "enum": ["pending", "in_progress", "done", "cancelled"],
                },
                "priority": {
                    "type": "string",
                    "description": "New priority: low, medium, high",
                    "enum": ["low", "medium", "high"],
                },
            },
            "required": ["task_id"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        task_id = input_data["task_id"]

        # 准备更新
        updates = {}
        for field in ["title", "description"]:
            if field in input_data:
                updates[field] = input_data[field]

        # 解析状态
        if "status" in input_data:
            try:
                updates["status"] = TaskStatus(input_data["status"])
            except ValueError:
                return ToolResult.err(f"Invalid status: {input_data['status']}")

        # 解析优先级
        if "priority" in input_data:
            try:
                updates["priority"] = TaskPriority(input_data["priority"])
            except ValueError:
                return ToolResult.err(f"Invalid priority: {input_data['priority']}")

        try:
            task = _task_store.update(task_id, **updates)

            if task is None:
                return ToolResult.err(f"Task not found: {task_id}")

            return ToolResult.ok(
                content=f"Task updated: {task.id}",
                metadata=task.to_dict()
            )

        except Exception as e:
            return ToolResult.err(f"Failed to update task: {e}")


class TaskListTool(Tool):
    """
    List tasks with optional filters.

    示例：
        task_list()
        task_list(status="pending")
        task_list(tags=["bug"])
    """

    name = "task_list"
    description = "List tasks with optional status and tag filters."
    permission = Permission(mode=PermissionMode.AUTOMATIC, scope=PermissionScope.READ)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by status: pending, in_progress, done, cancelled",
                    "enum": ["pending", "in_progress", "done", "cancelled"],
                },
                "priority": {
                    "type": "string",
                    "description": "Filter by priority: low, medium, high",
                    "enum": ["low", "medium", "high"],
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by tags (any match)",
                },
                "assignee": {
                    "type": "string",
                    "description": "Filter by assignee",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of tasks to return",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        status = input_data.get("status")
        priority = input_data.get("priority")
        tags = input_data.get("tags")
        assignee = input_data.get("assignee")
        limit = input_data.get("limit", 20)

        # 解析状态
        status_enum = None
        if status:
            try:
                status_enum = TaskStatus(status)
            except ValueError:
                return ToolResult.err(f"Invalid status: {status}")

        # 解析优先级
        priority_enum = None
        if priority:
            try:
                priority_enum = TaskPriority(priority)
            except ValueError:
                return ToolResult.err(f"Invalid priority: {priority}")

        try:
            tasks = _task_store.list(
                status=status_enum,
                priority=priority_enum,
                assignee=assignee,
            )

            # 过滤标签
            if tags:
                tasks = [t for t in tasks if any(tag in t.tags for tag in tags)]

            # 限制数量
            tasks = tasks[:limit]

            # 格式化输出
            if not tasks:
                return ToolResult.ok("No tasks found.")

            total = _task_store.count(status_enum)
            
            lines = [f"Tasks ({len(tasks)} of {total}):\n"]
            for task in tasks:
                status_icon = {
                    TaskStatus.PENDING: "○",
                    TaskStatus.IN_PROGRESS: "◐",
                    TaskStatus.DONE: "●",
                    TaskStatus.CANCELLED: "✗",
                }.get(task.status, "?")

                lines.append(f"{status_icon} [{task.id}] {task.title}")
                if task.priority == TaskPriority.HIGH:
                    lines[-1] += " 🔥"
                if task.tags:
                    lines.append(f"   Tags: {', '.join(task.tags)}")
                lines.append("")

            return ToolResult.ok(
                content="\n".join(lines[:-1]) if lines else "No tasks found.",
                metadata={"count": len(tasks), "total": total}
            )

        except Exception as e:
            return ToolResult.err(f"Failed to list tasks: {e}")
