"""
Server Module - Server Mode

服务器模式，允许 Claude Code 作为后台服务运行。
对应 Claude Code 源码: src/server/*.ts

功能：
- TCP 服务器模式
- HTTP API 端点
- WebSocket 实时通信
- RPC 调用接口
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


# 日志配置
logger = logging.getLogger("server")


@dataclass
class RPCRequest:
    """RPC 请求"""
    id: str
    method: str
    params: Dict[str, Any]


@dataclass
class RPCResponse:
    """RPC 响应"""
    id: str
    result: Optional[Any] = None
    error: Optional[str] = None


class ServerHandler(ABC):
    """服务器处理器基类"""

    @abstractmethod
    async def handle_request(self, request: RPCRequest) -> RPCResponse:
        """处理 RPC 请求"""
        ...

    @abstractmethod
    async def handle_connect(self, client_id: str) -> None:
        """客户端连接"""
        ...

    @abstractmethod
    async def handle_disconnect(self, client_id: str) -> None:
        """客户端断开"""
        ...


class TCPServer:
    """
    TCP 服务器。
    
    提供基于 TCP 的 RPC 接口。
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        handler: Optional[ServerHandler] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.handler = handler
        self._server: Optional[asyncio.Server] = None
        self._clients: Dict[str, asyncio.StreamWriter] = {}
        self._running = False

    async def start(self) -> None:
        """启动服务器"""
        if self._running:
            return

        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
        )

        self._running = True
        logger.info(f"TCP Server started on {self.host}:{self.port}")

        async with self._server:
            await self._server.serve_forever()

    async def stop(self) -> None:
        """停止服务器"""
        if not self._running:
            return

        self._running = False

        # 关闭所有客户端
        for writer in self._clients.values():
            writer.close()
            await writer.wait_closed()

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        logger.info("TCP Server stopped")

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """处理客户端连接"""
        addr = writer.get_extra_info("peername")
        client_id = f"{addr[0]}:{addr[1]}"
        self._clients[client_id] = writer

        logger.info(f"Client connected: {client_id}")

        if self.handler:
            await self.handler.handle_connect(client_id)

        try:
            while self._running:
                line = await reader.readline()
                if not line:
                    break

                try:
                    request = RPCRequest(**json.loads(line.decode()))
                except Exception as e:
                    logger.error(f"Failed to parse request: {e}")
                    continue

                if self.handler:
                    response = await self.handler.handle_request(request)
                    response_data = json.dumps({
                        "id": response.id,
                        "result": response.result,
                        "error": response.error,
                    })
                    writer.write(f"{response_data}\n".encode())
                    await writer.drain()

        except Exception as e:
            logger.error(f"Client error: {e}")

        finally:
            del self._clients[client_id]
            writer.close()
            await writer.wait_closed()

            if self.handler:
                await self.handler.handle_disconnect(client_id)

            logger.info(f"Client disconnected: {client_id}")


class HTTPServer:
    """
    HTTP 服务器。
    
    提供 REST API 端点。
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
    ) -> None:
        self.host = host
        self.port = port
        self._app: Optional[Any] = None
        self._running = False

    async def start(self) -> None:
        """启动 HTTP 服务器"""
        # 简单的 HTTP 服务器实现
        # 实际使用可以用 aiohttp 或类似的库
        logger.info(f"HTTP Server started on {self.host}:{self.port}")
        self._running = True

        # 这里需要实现实际的 HTTP 服务器逻辑
        # 简化实现示例：
        import asyncio

        async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
            data = await reader.read(1024)
            message = data.decode()

            # 简单的 HTTP 响应
            response = "HTTP/1.1 200 OK\r\n\r\nHello from Claude Code Server"
            writer.write(response.encode())
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(
            handler,
            self.host,
            self.port
        )

        async with server:
            await server.serve_forever()

    async def stop(self) -> None:
        """停止 HTTP 服务器"""
        self._running = False
        logger.info("HTTP Server stopped")


class WebSocketServer:
    """
    WebSocket 服务器。
    
    提供实时双向通信。
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8081,
    ) -> None:
        self.host = host
        self.port = port
        self._running = False

    async def start(self) -> None:
        """启动 WebSocket 服务器"""
        # WebSocket 需要专门的库如 websockets
        logger.info(f"WebSocket Server started on {self.host}:{self.port}")
        self._running = True

    async def stop(self) -> None:
        """停止 WebSocket 服务器"""
        self._running = False
        logger.info("WebSocket Server stopped")


# RPC 方法注册表
_rpc_methods: Dict[str, Callable] = {}


def register_rpc_method(name: str, handler: Callable) -> None:
    """注册 RPC 方法"""
    _rpc_methods[name] = handler


async def call_rpc_method(method: str, params: Dict[str, Any]) -> Any:
    """调用 RPC 方法"""
    if method not in _rpc_methods:
        raise ValueError(f"Unknown RPC method: {method}")
    return await _rpc_methods[method](**params)


__all__ = [
    "ServerHandler",
    "TCPServer",
    "HTTPServer",
    "WebSocketServer",
    "RPCRequest",
    "RPCResponse",
    "register_rpc_method",
    "call_rpc_method",
]
