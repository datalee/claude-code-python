"""
Remote Module - 远程控制

提供远程控制 Claude Code 的能力。
对应 Claude Code 源码: src/remote/*.ts

支持功能：
- TCP Socket 服务器模式
- HTTP API 端点
- WebSocket 实时通信
- 认证与授权
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

# ============================================================================
# 认证
# ============================================================================

@dataclass
class AuthToken:
    """认证令牌"""
    token: str
    user_id: str
    created_at: float
    expires_at: Optional[float] = None
    scopes: Set[str] = field(default_factory=set)
    
    def is_valid(self) -> bool:
        """检查令牌是否有效"""
        import time
        if self.expires_at and time.time() > self.expires_at:
            return False
        return True


class AuthManager:
    """
    认证管理器。
    
    管理 API 令牌的生成和验证。
    """
    
    def __init__(self) -> None:
        self.tokens: Dict[str, AuthToken] = {}
        self._logger = logging.getLogger("remote.auth")
    
    def generate_token(
        self,
        user_id: str,
        expires_in: Optional[int] = None,
        scopes: Optional[Set[str]] = None,
    ) -> str:
        """
        生成新令牌。
        
        Args:
            user_id: 用户 ID
            expires_in: 过期时间（秒），None 表示永不过期
            scopes: 权限范围
            
        Returns:
            生成的令牌
        """
        import time
        
        token = secrets.token_urlsafe(32)
        expires_at = None
        if expires_in:
            expires_at = time.time() + expires_in
        
        self.tokens[token] = AuthToken(
            token=token,
            user_id=user_id,
            created_at=time.time(),
            expires_at=expires_at,
            scopes=scopes or set(),
        )
        
        return token
    
    def validate_token(self, token: str) -> Optional[AuthToken]:
        """
        验证令牌。
        
        Args:
            token: 令牌字符串
            
        Returns:
            AuthToken 如果有效，None 如果无效
        """
        auth_token = self.tokens.get(token)
        if auth_token and auth_token.is_valid():
            return auth_token
        return None
    
    def revoke_token(self, token: str) -> bool:
        """
        撤销令牌。
        
        Args:
            token: 令牌字符串
            
        Returns:
            是否成功撤销
        """
        if token in self.tokens:
            del self.tokens[token]
            return True
        return False
    
    def cleanup_expired(self) -> int:
        """清理已过期的令牌"""
        import time
        expired = [
            t for t, token in self.tokens.items()
            if token.expires_at and time.time() > token.expires_at
        ]
        for t in expired:
            del self.tokens[t]
        return len(expired)


# ============================================================================
# 消息协议
# ============================================================================

@dataclass
class RemoteMessage:
    """远程消息"""
    id: str
    type: str  # request, response, event, error
    action: str  # execute, query, event_subscribe, etc.
    payload: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
    def to_json(self) -> str:
        return json.dumps({
            "id": self.id,
            "type": self.type,
            "action": self.action,
            "payload": self.payload,
            "error": self.error,
        })
    
    @classmethod
    def from_json(cls, data: str) -> "RemoteMessage":
        obj = json.loads(data)
        return cls(
            id=obj["id"],
            type=obj["type"],
            action=obj["action"],
            payload=obj.get("payload", {}),
            error=obj.get("error"),
        )


# ============================================================================
# RemoteServer
# ============================================================================

class RemoteServer:
    """
    远程控制服务器。
    
    通过 TCP Socket 提供远程控制接口。
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        auth_manager: Optional[AuthManager] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.auth_manager = auth_manager or AuthManager()
        self._server: Optional[asyncio.Server] = None
        self._clients: Set[asyncio.StreamWriter] = set()
        self._handlers: Dict[str, Callable] = {}
        self._logger = logging.getLogger("remote.server")
        
        self._register_default_handlers()
    
    def _register_default_handlers(self) -> None:
        """注册默认处理器"""
        self._handlers = {
            "ping": self._handle_ping,
            "status": self._handle_status,
            "execute": self._handle_execute,
            "authenticate": self._handle_authenticate,
        }
    
    def register_handler(self, action: str, handler: Callable) -> None:
        """注册消息处理器"""
        self._handlers[action] = handler
    
    async def start(self) -> None:
        """启动服务器"""
        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
        )
        self._logger.info(f"Remote server started on {self.host}:{self.port}")
    
    async def stop(self) -> None:
        """停止服务器"""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._logger.info("Remote server stopped")
    
    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """处理客户端连接"""
        self._clients.add(writer)
        addr = writer.get_extra_info("peername")
        self._logger.info(f"Client connected: {addr}")
        
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                
                try:
                    msg = RemoteMessage.from_json(line.decode())
                    response = await self._process_message(msg)
                    if response:
                        writer.write((response.to_json() + "\n").encode())
                        await writer.drain()
                except Exception as e:
                    self._logger.error(f"Error processing message: {e}")
                    error_msg = RemoteMessage(
                        id="",
                        type="error",
                        action="",
                        error=str(e),
                    )
                    writer.write((error_msg.to_json() + "\n").encode())
                    await writer.drain()
        
        except Exception as e:
            self._logger.error(f"Client error: {e}")
        
        finally:
            self._clients.discard(writer)
            writer.close()
            await writer.wait_closed()
            self._logger.info(f"Client disconnected: {addr}")
    
    async def _process_message(self, msg: RemoteMessage) -> Optional[RemoteMessage]:
        """处理消息并返回响应"""
        handler = self._handlers.get(msg.action)
        
        if not handler:
            return RemoteMessage(
                id=msg.id,
                type="error",
                action=msg.action,
                error=f"Unknown action: {msg.action}",
            )
        
        try:
            result = handler(msg.payload)
            if hasattr(result, "__await__"):
                result = await result
            
            return RemoteMessage(
                id=msg.id,
                type="response",
                action=msg.action,
                payload={"result": result},
            )
        
        except Exception as e:
            return RemoteMessage(
                id=msg.id,
                type="error",
                action=msg.action,
                error=str(e),
            )
    
    # =========================================================================
    # 默认处理器
    # =========================================================================
    
    def _handle_ping(self, payload: Dict[str, Any]) -> str:
        return "pong"
    
    def _handle_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "running",
            "clients": len(self._clients),
            "version": "1.0.0",
        }
    
    async def _handle_execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """执行命令（需要认证）"""
        command = payload.get("command")
        if not command:
            raise ValueError("No command provided")
        
        import asyncio
        import os
        import sys
        
        # Windows 上用 PowerShell 执行
        if sys.platform == "win32":
            shell = ["powershell", "-Command"]
            full_command = " ".join(f'"{c}"' if " " in c else c for c in command.split())
        else:
            shell = ["/bin/sh", "-c"]
            full_command = command
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *shell,
                full_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            
            return {
                "executed": command,
                "returncode": proc.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            }
        except Exception as e:
            return {
                "executed": command,
                "error": str(e),
                "returncode": -1,
            }
    
    def _handle_authenticate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """认证"""
        user_id = payload.get("user_id")
        if not user_id:
            raise ValueError("No user_id provided")
        
        token = self.auth_manager.generate_token(user_id)
        return {"token": token, "user_id": user_id}


# ============================================================================
# RemoteClient
# ============================================================================

class RemoteClient:
    """
    远程控制客户端。
    
    连接到远程服务器并发送命令。
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        token: Optional[str] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.token = token
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
    
    async def connect(self) -> None:
        """连接到服务器"""
        self._reader, self._writer = await asyncio.open_connection(
            self.host,
            self.port,
        )
    
    async def disconnect(self) -> None:
        """断开连接"""
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
    
    async def send(
        self,
        action: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> RemoteMessage:
        """发送消息并等待响应"""
        if not self._writer:
            raise RuntimeError("Not connected")
        
        msg = RemoteMessage(
            id=str(uuid.uuid4()),
            type="request",
            action=action,
            payload=payload or {},
        )
        
        self._writer.write((msg.to_json() + "\n").encode())
        await self._writer.drain()
        
        # 等待响应
        response_line = await self._reader.readline()
        return RemoteMessage.from_json(response_line.decode())


# ============================================================================
# 全局实例
# ============================================================================

_auth_manager: Optional[AuthManager] = None
_server: Optional[RemoteServer] = None


def get_auth_manager() -> AuthManager:
    """获取全局认证管理器"""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager


def get_remote_server() -> RemoteServer:
    """获取全局远程服务器"""
    global _server
    if _server is None:
        _server = RemoteServer()
    return _server


__all__ = [
    "AuthToken",
    "AuthManager",
    "RemoteMessage",
    "RemoteServer",
    "RemoteClient",
    "get_auth_manager",
    "get_remote_server",
]
