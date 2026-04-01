"""
AgentTool - 子 Agent 启动工具

在当前会话中启动子 Agent 来完成任务。
对应 Claude Code 内置工具: AgentTool
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Dict, List, Optional

from tool.base import Tool, ToolResult, Permission, PermissionScope, PermissionMode


class AgentTool(Tool):
    """
    Spawn a sub-agent to accomplish a task.

    The sub-agent runs in the same process and can use the same tools.
    Results from the sub-agent are returned to the parent agent.

    示例：
        agent(
            task="Read all files in ./src and summarize the architecture",
            model="claude-opus-4-20250514"
        )
    """

    name = "agent"
    description = "Spawn a sub-agent to accomplish a task. The sub-agent can use tools and returns results to the parent."
    permission = Permission(mode=PermissionMode.ASK, scope=PermissionScope.ALL)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task for the sub-agent to accomplish",
                },
                "model": {
                    "type": "string",
                    "description": "Model to use for the sub-agent (default: same as parent)",
                },
                "max_iterations": {
                    "type": "integer",
                    "description": "Maximum iterations for the sub-agent",
                    "default": 50,
                },
                "prompt": {
                    "type": "string",
                    "description": "Additional instructions for the sub-agent",
                },
            },
            "required": ["task"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        from agent.query_engine import QueryEngine, AgentConfig
        from agent.context import AgentContext

        task = input_data["task"]
        model = input_data.get("model")
        max_iterations = input_data.get("max_iterations", 50)
        prompt = input_data.get("prompt")

        try:
            # 创建子 Agent 配置
            config = AgentConfig(
                model=model or "claude-sonnet-4-20250514",
                max_iterations=max_iterations,
                stream=False,  # 子 agent 不流式输出
            )

            # 创建子 Agent 上下文
            system_prompt = prompt or "You are a helpful assistant."
            context = AgentContext(system_prompt=system_prompt)

            # 创建子 Agent
            agent = QueryEngine(config=config)
            agent.context = context

            # 运行子 Agent
            result = await agent.run(task)

            return ToolResult.ok(
                content=result,
                metadata={
                    "iterations": agent.iteration,
                }
            )

        except Exception as e:
            return ToolResult.err(f"Agent execution error: {e}")


class TeamCreateTool(Tool):
    """
    Create a team of agents that can collaborate.

    团队成员可以：
    - 互相发送消息
    - 分工合作
    - 汇总结果

    示例：
        team = team_create(
            name="project-team",
            agents=[
                {"name": "coder", "task": "Write the code"},
                {"name": "reviewer", "task": "Review the code"},
            ]
        )
    """

    name = "team_create"
    description = "Create a team of agents that can collaborate on tasks."
    permission = Permission(mode=PermissionMode.ASK, scope=PermissionScope.ALL)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Team name",
                },
                "agents": {
                    "type": "array",
                    "description": "List of agent configurations",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "role": {"type": "string"},
                            "task": {"type": "string"},
                            "model": {"type": "string"},
                        },
                    },
                },
                "wait_for_completion": {
                    "type": "boolean",
                    "description": "Wait for all agents to complete",
                    "default": True,
                },
            },
            "required": ["name", "agents"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        name = input_data["name"]
        agents_config = input_data["agents"]
        wait = input_data.get("wait_for_completion", True)

        try:
            # 创建团队
            team = AgentTeam(name=name)

            # 创建并注册 agents
            for config in agents_config:
                agent = team.create_agent(
                    name=config["name"],
                    role=config.get("role", config["name"]),
                    task=config.get("task", ""),
                    model=config.get("model"),
                )
                team.register(agent)

            # 启动团队
            if wait:
                results = await team.run()
                return ToolResult.ok(
                    content=f"Team '{name}' completed with {len(results)} results",
                    metadata={"results": results}
                )
            else:
                # 异步启动
                asyncio.create_task(team.run())
                return ToolResult.ok(
                    content=f"Team '{name}' started asynchronously",
                    metadata={"team_id": team.id}
                )

        except Exception as e:
            return ToolResult.err(f"Team creation error: {e}")


class AgentTeam:
    """
    Agent 团队管理器。

    管理多个 Agent 的生命周期和协作。
    """

    def __init__(self, name: str) -> None:
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.agents: Dict[str, Any] = {}  # name -> agent
        self.results: Dict[str, Any] = {}
        self._running = False

    def create_agent(self, name: str, role: str, task: str, model: Optional[str] = None):
        """创建一个团队成员 Agent"""
        from agent.query_engine import QueryEngine, AgentConfig

        config = AgentConfig(
            model=model or "claude-sonnet-4-20250514",
            max_iterations=30,
        )

        system_prompt = f"""You are {role}.
Your task: {task}
Work together with other team members to accomplish the goal."""

        context = AgentContext(system_prompt=system_prompt)
        agent = QueryEngine(config=config)
        agent.context = context

        self.agents[name] = {
            "agent": agent,
            "role": role,
            "task": task,
        }

        return agent

    def register(self, agent) -> None:
        """注册 agent（兼容接口）"""
        pass  # create_agent 已经注册

    async def run(self) -> Dict[str, Any]:
        """运行所有 team members"""
        self._running = True

        # 并行运行所有 agent
        tasks = []
        for name, info in self.agents.items():
            agent = info["agent"]
            task = info["task"]
            tasks.append(self._run_agent(name, agent, task))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 收集结果
        for i, name in enumerate(self.agents.keys()):
            result = results[i]
            if isinstance(result, Exception):
                self.results[name] = {"error": str(result)}
            else:
                self.results[name] = {"result": result}

        self._running = False
        return self.results

    async def _run_agent(self, name: str, agent, task: str) -> str:
        """运行单个 agent"""
        return await agent.run(task)

    async def send_message(self, from_name: str, to_name: str, message: str) -> None:
        """向团队成员发送消息"""
        if to_name not in self.agents:
            raise ValueError(f"Unknown agent: {to_name}")

        # 存储消息供后续处理
        if "messages" not in self.agents[to_name]:
            self.agents[to_name]["messages"] = []
        self.agents[to_name]["messages"].append({
            "from": from_name,
            "content": message,
        })

    def get_results(self) -> Dict[str, Any]:
        """获取所有结果"""
        return self.results
