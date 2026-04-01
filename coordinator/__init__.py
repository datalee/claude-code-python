"""
Coordinator - 多 Agent 协作系统

协调多个 Agent 完成复杂任务。
对应 Claude Code 源码: src/coordinator/*.ts
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from agent.query_engine import QueryEngine, AgentConfig, AgentState
from agent.context import AgentContext


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class CoordinatorTask:
    """协调任务"""
    id: str
    description: str
    assigned_to: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None


@dataclass
class AgentInfo:
    """Agent 信息"""
    id: str
    name: str
    role: str
    agent: QueryEngine
    state: AgentState = AgentState.IDLE
    current_task: Optional[str] = None
    completed_tasks: List[str] = field(default_factory=list)


class Coordinator:
    """
    多 Agent 协作协调器。

    职责：
    1. 管理多个 Agent 的生命周期
    2. 分配任务给空闲 Agent
    3. 处理 Agent 间的消息传递
    4. 汇总最终结果

    对应 Claude Code 源码: src/coordinator/Coordinator.ts

    示例：
        coord = Coordinator()

        # 添加 Agent
        coord.add_agent(
            id="coder",
            name="Coder",
            role="Write Python code"
        )
        coord.add_agent(
            id="reviewer",
            name="Reviewer",
            role="Review code for bugs"
        )

        # 添加任务
        coord.add_task("Write a REST API")
        coord.add_task("Review the API implementation")

        # 运行
        results = await coord.run()
    """

    def __init__(
        self,
        name: str = "coordinator",
        max_concurrent: int = 3,
    ) -> None:
        """
        初始化协调器。

        Args:
            name: 协调器名称
            max_concurrent: 最大并发 Agent 数
        """
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.max_concurrent = max_concurrent

        self._agents: Dict[str, AgentInfo] = {}
        self._tasks: Dict[str, CoordinatorTask] = {}
        self._running = False
        self._results: Dict[str, Any] = {}

    def add_agent(
        self,
        id: str,
        name: str,
        role: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> None:
        """
        添加一个 Agent。

        Args:
            id: Agent 唯一标识
            name: Agent 显示名称
            role: Agent 角色描述
            model: 使用的模型
            system_prompt: 自定义系统提示
        """
        prompt = system_prompt or f"""You are {name}, a {role}.
Work on tasks assigned to you by the coordinator.
Report your results clearly and concisely."""

        config = AgentConfig(
            model=model or "claude-sonnet-4-20250514",
            max_iterations=50,
            stream=False,
        )

        context = AgentContext(system_prompt=prompt)
        agent = QueryEngine(config=config)
        agent.context = context

        self._agents[id] = AgentInfo(
            id=id,
            name=name,
            role=role,
            agent=agent,
        )

    def add_task(
        self,
        description: str,
        assigned_to: Optional[str] = None,
        depends_on: Optional[List[str]] = None,
    ) -> str:
        """
        添加一个任务。

        Args:
            description: 任务描述
            assigned_to: 指定执行的 Agent ID
            depends_on: 依赖的任务 ID 列表

        Returns:
            任务 ID
        """
        task_id = f"task_{len(self._tasks)}"
        task = CoordinatorTask(
            id=task_id,
            description=description,
            assigned_to=assigned_to,
        )
        self._tasks[task_id] = task
        return task_id

    async def run(self) -> Dict[str, Any]:
        """
        运行协调器。

        Returns:
            所有任务的结果字典
        """
        self._running = True
        self._results = {}

        try:
            # 运行主循环
            await self._run_loop()
        finally:
            self._running = False

        return self._results

    async def _run_loop(self) -> None:
        """主协调循环"""
        while self._running:
            # 检查是否全部完成
            if self._all_tasks_done():
                break

            # 分配并运行可执行的任务
            await self._process_ready_tasks()

            # 等待一小段时间
            await asyncio.sleep(0.1)

    def _all_tasks_done(self) -> bool:
        """检查是否所有任务都完成"""
        for task in self._tasks.values():
            if task.status not in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED):
                return False
        return len(self._tasks) > 0

    async def _process_ready_tasks(self) -> None:
        """处理准备好的任务"""
        # 获取空闲 Agent
        idle_agents = [
            info for info in self._agents.values()
            if info.state == AgentState.IDLE
        ]

        # 获取可执行的任务（依赖已满足）
        ready_tasks = [
            task for task in self._tasks.values()
            if self._is_task_ready(task)
        ]

        # 分配任务
        for task in ready_tasks[:len(idle_agents)]:
            # 找到合适的 Agent
            agent = self._find_agent_for_task(task, idle_agents)
            if agent:
                asyncio.create_task(self._execute_task(task, agent))

    def _is_task_ready(self, task: CoordinatorTask) -> bool:
        """检查任务是否准备好执行"""
        if task.status != TaskStatus.PENDING:
            return False

        # 如果有指定 Agent，检查是否空闲
        if task.assigned_to:
            if task.assigned_to not in self._agents:
                return False
            if self._agents[task.assigned_to].state != AgentState.IDLE:
                return False
            return True

        # 检查依赖是否都已完成
        # (depends_on 字段目前简化处理)
        return True

    def _find_agent_for_task(
        self,
        task: CoordinatorTask,
        idle_agents: List[AgentInfo],
    ) -> Optional[AgentInfo]:
        """为任务找到合适的 Agent"""
        if task.assigned_to:
            return self._agents.get(task.assigned_to)
        return idle_agents[0] if idle_agents else None

    async def _execute_task(self, task: CoordinatorTask, agent_info: AgentInfo) -> None:
        """执行单个任务"""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now().timestamp()
        agent_info.state = AgentState.RUNNING
        agent_info.current_task = task.id

        try:
            # 运行 Agent
            result = await agent_info.agent.run(task.description)

            # 保存结果
            task.status = TaskStatus.DONE
            task.result = result
            task.completed_at = datetime.now().timestamp()
            self._results[task.id] = result

            agent_info.completed_tasks.append(task.id)

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)

        finally:
            agent_info.state = AgentState.IDLE
            agent_info.current_task = None

    def get_status(self) -> Dict[str, Any]:
        """获取协调器状态"""
        return {
            "id": self.id,
            "name": self.name,
            "running": self._running,
            "agents": {
                id: {
                    "name": info.name,
                    "state": info.state.value,
                    "current_task": info.current_task,
                    "completed_tasks": len(info.completed_tasks),
                }
                for id, info in self._agents.items()
            },
            "tasks": {
                id: {
                    "description": task.description,
                    "status": task.status.value,
                    "assigned_to": task.assigned_to,
                    "result": task.result[:100] + "..." if task.result and len(task.result) > 100 else task.result,
                }
                for id, task in self._tasks.items()
            },
        }

    def stop(self) -> None:
        """停止协调器"""
        self._running = False
