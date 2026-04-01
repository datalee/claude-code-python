"""
MCP - Model Context Protocol 集成

MCP 是一种让 AI 与外部工具和数据源连接的协议。
对应 Claude Code 源码: src/mcp/*.ts
参考: https://modelcontextprotocol.io/
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union


class MCPError(Exception):
    """MCP 相关错误"""
    pass


class MCPConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    annotations: Optional[Dict[str, Any]] = None


@dataclass
class MCPResource:
    """MCP 资源定义"""
    uri: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None


@dataclass
class MCPResponse:
    """MCP 响应"""
    success: bool
    data: Any = None
    error: Optional[str] = None


class MCPClient:
    """
    MCP 客户端。

    通过 stdio 或 HTTP 连接到 MCP 服务器。
    """

    def __init__(
        self,
        command: Optional[List[str]] = None,
        url: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        初始化 MCP 客户端。

        Args:
            command: 启动命令（用于 stdio 连接），如 ["npx", "mcp-server"]
            url: 服务器 URL（用于 HTTP 连接）
            env: 环境变量
        """
        self.command = command
        self.url = url
        self.env = env or os.environ.copy()

        self._process: Optional[asyncio.subprocess.Process] = None
        self._state = MCPConnectionState.DISCONNECTED
        self._request_id = 0
        self._lock = asyncio.Lock()

        self._tools: Dict[str, MCPTool] = {}
        self._resources: Dict[str, MCPResource] = {}

    async def connect(self) -> None:
        """连接到 MCP 服务器"""
        if self._state == MCPConnectionState.CONNECTED:
            return

        self._state = MCPConnectionState.CONNECTING

        try:
            if self.command:
                # Stdio 连接
                self._process = await asyncio.create_subprocess_exec(
                    *self.command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=self.env,
                )
            elif self.url:
                # HTTP 连接（后续实现）
                raise NotImplementedError("HTTP MCP not yet implemented")
            else:
                raise MCPError("Must provide either command or url")

            # 初始化握手
            await self._initialize()

            self._state = MCPConnectionState.CONNECTED

        except Exception as e:
            self._state = MCPConnectionState.ERROR
            raise MCPError(f"Failed to connect: {e}")

    async def disconnect(self) -> None:
        """断开 MCP 服务器连接"""
        if self._process:
            self._process.terminate()
            await self._process.wait()
            self._process = None

        self._state = MCPConnectionState.DISCONNECTED

    async def _initialize(self) -> None:
        """发送初始化请求"""
        request = self._make_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True},
                "sampling": {},
            },
            "clientInfo": {
                "name": "claude-code-python",
                "version": "1.0.0",
            },
        })

        response = await self._send(request)

        # 获取服务器提供的工具和资源
        if "tools" in response.get("result", {}).get("tools", []):
            for tool in response["result"]["tools"]:
                self._tools[tool["name"]] = MCPTool(**tool)

        if "resources" in response.get("result", {}):
            for resource in response["result"]["resources"]:
                self._resources[resource["uri"]] = MCPResource(**resource)

    async def list_tools(self) -> List[MCPTool]:
        """列出所有可用工具"""
        request = self._make_request("tools/list", {})
        response = await self._send(request)
        return [MCPTool(**t) for t in response.get("result", {}).get("tools", [])]

    async def call_tool(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> MCPResponse:
        """
        调用 MCP 工具。

        Args:
            name: 工具名称
            arguments: 工具参数

        Returns:
            MCPResponse
        """
        request = self._make_request("tools/call", {
            "name": name,
            "arguments": arguments or {},
        })

        response = await self._send(request)

        if "error" in response:
            return MCPResponse(success=False, error=response["error"])

        return MCPResponse(success=True, data=response.get("result"))

    async def list_resources(self) -> List[MCPResource]:
        """列出所有可用资源"""
        request = self._make_request("resources/list", {})
        response = await self._send(request)
        return [MCPResource(**r) for r in response.get("result", {}).get("resources", [])]

    async def read_resource(self, uri: str) -> str:
        """读取资源内容"""
        request = self._make_request("resources/read", {"uri": uri})
        response = await self._send(request)
        return response.get("result", {}).get("contents", [{}])[0].get("text", "")

    # -------------------------------------------------------------------------
    # 协议消息处理
    # -------------------------------------------------------------------------

    def _make_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """创建 JSON-RPC 请求"""
        self._request_id += 1
        return {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }

    async def _send(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """发送请求并等待响应"""
        if not self._process:
            raise MCPError("Not connected")

        async with self._lock:
            # 发送请求
            message = json.dumps(request) + "\n"
            self._process.stdin.write(message)
            await self._process.stdin.drain()

            # 读取响应
            line = await self._process.stdout.readline()
            if not line:
                raise MCPError("Server closed connection")

            return json.loads(line)

    @property
    def state(self) -> MCPConnectionState:
        return self._state

    @property
    def tools(self) -> Dict[str, MCPTool]:
        return self._tools

    @property
    def resources(self) -> Dict[str, MCPResource]:
        return self._resources


class MCPToolAdapter:
    """
    将 MCP 工具适配为本地 Tool 接口。

    允许 MCP 服务器提供的工具在本地 Tool 系统中使用。
    """

    def __init__(self, mcp_client: MCPClient, tool_name: str) -> None:
        """
        初始化 MCP 工具适配器。

        Args:
            mcp_client: MCP 客户端
            tool_name: MCP 工具名称
        """
        self._client = mcp_client
        self._tool_name = tool_name
        self._mcp_tool: Optional[MCPTool] = None

    async def discover(self) -> None:
        """发现并缓存工具定义"""
        tools = await self._client.list_tools()
        for tool in tools:
            if tool.name == self._tool_name:
                self._mcp_tool = tool
                break

    def get_metadata(self) -> Dict[str, Any]:
        """获取工具元数据"""
        if not self._mcp_tool:
            raise MCPError(f"Tool not discovered: {self._tool_name}")

        return {
            "name": self._mcp_tool.name,
            "description": self._mcp_tool.description,
            "input_schema": self._mcp_tool.input_schema,
        }

    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具"""
        response = await self._client.call_tool(self._tool_name, arguments)

        if not response.success:
            raise MCPError(response.error or "Unknown error")

        return response.data or {}


class MCPManager:
    """
    MCP 管理器。

    管理多个 MCP 客户端连接。
    """

    def __init__(self) -> None:
        self._clients: Dict[str, MCPClient] = {}

    async def add_server(
        self,
        name: str,
        command: Optional[List[str]] = None,
        url: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        添加 MCP 服务器。

        Args:
            name: 服务器名称
            command: 启动命令（stdio 连接）
            url: 服务器 URL（HTTP 连接）
            env: 环境变量
        """
        client = MCPClient(command=command, url=url, env=env)
        await client.connect()
        self._clients[name] = client

    async def remove_server(self, name: str) -> None:
        """移除 MCP 服务器"""
        if name in self._clients:
            await self._clients[name].disconnect()
            del self._clients[name]

    def get_client(self, name: str) -> Optional[MCPClient]:
        """获取 MCP 客户端"""
        return self._clients.get(name)

    def list_servers(self) -> List[Dict[str, Any]]:
        """列出所有服务器"""
        return [
            {
                "name": name,
                "state": client.state.value,
                "tool_count": len(client.tools),
                "resource_count": len(client.resources),
            }
            for name, client in self._clients.items()
        ]

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> MCPResponse:
        """调用指定服务器的 tools"""
        client = self._clients.get(server_name)
        if not client:
            return MCPResponse(success=False, error=f"Server not found: {server_name}")

        return await client.call_tool(tool_name, arguments)

    async def list_tools(self, server_name: Optional[str] = None) -> Dict[str, List[MCPTool]]:
        """列出工具（可指定服务器）"""
        if server_name:
            client = self._clients.get(server_name)
            if not client:
                return {}
            return {server_name: await client.list_tools()}

        result = {}
        for name, client in self._clients.items():
            result[name] = await client.list_tools()
        return result
