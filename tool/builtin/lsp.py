"""
LSP Tool - Language Server Protocol 集成

通过 LSP 提供代码跳转、定义查询、引用搜索等功能。
对应 Claude Code 内置工具: LSPTool

LSP 是一种协议，允许编辑器与语言服务器通信获取：
- 符号定义跳转 (go-to definition)
- 符号引用 (find references)
- 符号补全 (completion)
- 诊断信息 (diagnostics)
- 悬停文档 (hover)
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from tool.base import Tool, ToolResult, Permission, PermissionScope, PermissionMode


class LSPClient:
    """
    轻量级 LSP 客户端。

    通过 stdio 连接 LSP 服务器（如 pyright、typescript-language-server 等）。
    """

    def __init__(self, command: List[str], cwd: Optional[str] = None) -> None:
        self.command = command
        self.cwd = cwd or os.getcwd()
        self._process: Optional[asyncio.subprocess.Process] = None
        self._request_id = 0
        self._responses: Dict[int, asyncio.Future] = {}
        self._initialized = False

    async def start(self) -> None:
        """启动 LSP 服务器"""
        self._process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.cwd,
        )
        await self._send_initialize()

    async def stop(self) -> None:
        """停止 LSP 服务器"""
        if self._process:
            self._process.terminate()
            await self._process.wait()

    async def _send_initialize(self) -> None:
        """发送 initialize 请求"""
        # 发送 initialize
        init_request = self._make_request("initialize", {
            "processId": os.getpid(),
            "rootUri": Path(self.cwd).resolve().as_uri(),
            "capabilities": {
                "textDocument": {
                    "synchronization": {"didSave": True},
                    "definition": {"dynamicRegistration": True},
                    "references": {"dynamicRegistration": True},
                    "completion": {"dynamicRegistration": True},
                    "hover": {"dynamicRegistration": True},
                },
                "workspace": {
                    "applyEdit": True,
                    "workspaceFolders": True,
                },
            },
        })

        response = await self._send_request(init_request)
        self._initialized = True

        # 发送 initialized
        await self._send_notification("initialized", {})

    def _make_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """创建 JSON-RPC 请求"""
        self._request_id += 1
        return {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }

    async def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """发送请求并等待响应"""
        if not self._process:
            raise RuntimeError("LSP server not started")

        future = asyncio.Future()
        self._responses[request["id"]] = future

        # 发送请求
        message = json.dumps(request) + "\n"
        self._process.stdin.write(message)
        await self._process.stdin.drain()

        try:
            return await asyncio.wait_for(future, timeout=30)
        finally:
            self._responses.pop(request["id"], None)

    async def _send_notification(self, method: str, params: Dict[str, Any]) -> None:
        """发送通知（不需要响应）"""
        if not self._process:
            raise RuntimeError("LSP server not started")

        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        message = json.dumps(notification) + "\n"
        self._process.stdin.write(message)
        await self._process.stdin.drain()

    async def listen(self) -> None:
        """监听服务器消息"""
        if not self._process:
            raise RuntimeError("LSP server not started")

        while True:
            line = await self._process.stdout.readline()
            if not line:
                break

            try:
                message = json.loads(line)
                if "id" in message:
                    # 响应
                    future = self._responses.pop(message["id"], None)
                    if future and not future.done():
                        future.set_result(message.get("result", {}))
            except json.JSONDecodeError:
                continue

    async def text_document_did_open(
        self,
        uri: str,
        language_id: str,
        text: str,
    ) -> None:
        """通知文档打开"""
        await self._send_notification("textDocument/didOpen", {
            "textDocument": {
                "uri": uri,
                "languageId": language_id,
                "version": 1,
                "text": text,
            }
        })

    async def text_document_did_save(self, uri: str, text: str) -> None:
        """通知文档保存"""
        await self._send_notification("textDocument/didSave", {
            "textDocument": {"uri": uri},
            "text": text,
        })

    async def text_document_definition(
        self,
        uri: str,
        line: int,
        character: int,
    ) -> List[Dict[str, Any]]:
        """获取符号定义"""
        request = self._make_request("textDocument/definition", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
        })
        result = await self._send_request(request)
        locations = result.get("result", [])
        if isinstance(locations, dict):
            return [locations]
        return locations or []

    async def text_document_references(
        self,
        uri: str,
        line: int,
        character: int,
        include_declaration: bool = True,
    ) -> List[Dict[str, Any]]:
        """获取符号引用"""
        request = self._make_request("textDocument/references", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
            "context": {"includeDeclaration": include_declaration},
        })
        result = await self._send_request(request)
        locations = result.get("result", [])
        if isinstance(locations, dict):
            return [locations]
        return locations or []

    async def text_document_hover(
        self,
        uri: str,
        line: int,
        character: int,
    ) -> Optional[Dict[str, Any]]:
        """获取悬停信息"""
        request = self._make_request("textDocument/hover", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
        })
        result = await self._send_request(request)
        return result.get("result")

    async def text_document_completion(
        self,
        uri: str,
        line: int,
        character: int,
    ) -> List[Dict[str, Any]]:
        """获取补全列表"""
        request = self._make_request("textDocument/completion", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
        })
        result = await self._send_request(request)
        items = result.get("result", [])
        if isinstance(items, dict):
            return items.get("items", [])
        return items or []


# LSP 服务器配置
LSP_SERVERS = {
    "python": {
        "pyright": ["npx", "pyright-langserver", "--stdio"],
        "pylsp": ["pylsp"],
    },
    "typescript": {
        "tsserver": ["typescript-language-server", "--stdio"],
        "ts-ls": ["tsserver", "--stdio"],
    },
    "javascript": {
        "tsserver": ["typescript-language-server", "--stdio"],
    },
    "rust": {
        "rust-analyzer": ["rust-analyzer"],
    },
    "go": {
        "gopls": ["gopls"],
    },
}


class LSPTool(Tool):
    """
    Language Server Protocol 工具。

    提供代码跳转、定义查询、引用搜索等功能。

    示例：
        # 查找符号定义
        lsp_tool(goto="definition", path="./src/main.py", line=10, column=5)

        # 查找引用
        lsp_tool(goto="references", path="./src/main.py", line=10, column=5)

        # 获取悬停信息
        lsp_tool(goto="hover", path="./src/main.py", line=10, column=5)
    """

    name = "lsp"
    description = "Query code definitions, references, and hover info using Language Server Protocol."
    permission = Permission(mode=PermissionMode.AUTOMATIC, scope=PermissionScope.READ)

    def __init__(self):
        super().__init__()
        self._clients: Dict[str, LSPClient] = {}  # language -> client
        self._language_map = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".rs": "rust",
            ".go": "go",
        }

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "goto": {
                    "type": "string",
                    "description": "LSP method: definition, references, hover, completion",
                    "enum": ["definition", "references", "hover", "completion"],
                },
                "path": {
                    "type": "string",
                    "description": "File path",
                },
                "line": {
                    "type": "integer",
                    "description": "Line number (1-indexed)",
                },
                "column": {
                    "type": "integer",
                    "description": "Column number (0-indexed)",
                },
                "language": {
                    "type": "string",
                    "description": "Language override (e.g., python, typescript)",
                },
            },
            "required": ["goto", "path", "line", "column"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        goto = input_data["goto"]
        path = input_data["path"]
        line = input_data["line"]
        column = input_data["column"]
        language = input_data.get("language")

        try:
            # 确定语言
            if not language:
                ext = Path(path).suffix
                language = self._language_map.get(ext, "python")

            # 获取或创建 client
            client = await self._get_client(language)

            # 转换行号为 0-indexed
            lsp_line = line - 1

            # 执行 LSP 请求
            uri = Path(path).resolve().as_uri()

            if goto == "definition":
                result = await client.text_document_definition(uri, lsp_line, column)
                return self._format_locations(result, "definitions")

            elif goto == "references":
                result = await client.text_document_references(uri, lsp_line, column)
                return self._format_locations(result, "references")

            elif goto == "hover":
                result = await client.text_document_hover(uri, lsp_line, column)
                return self._format_hover(result)

            elif goto == "completion":
                result = await client.text_document_completion(uri, lsp_line, column)
                return self._format_completions(result)

            else:
                return ToolResult.err(f"Unknown goto: {goto}")

        except FileNotFoundError:
            return ToolResult.err(
                f"LSP server not found. Install with:\n"
                f"  Python: npm install -g pyright\n"
                f"  TypeScript: npm install -g typescript-language-server"
            )
        except Exception as e:
            return ToolResult.err(f"LSP error: {e}")

    async def _get_client(self, language: str) -> LSPClient:
        """获取或创建 LSP 客户端"""
        if language in self._clients:
            return self._clients[language]

        # 查找可用的 LSP 服务器
        servers = LSP_SERVERS.get(language, {})
        for name, command in servers.items():
            try:
                client = LSPClient(command=command)
                await client.start()
                self._clients[language] = client
                return client
            except FileNotFoundError:
                continue

        raise FileNotFoundError(f"No LSP server found for {language}")

    def _format_locations(
        self,
        locations: List[Dict[str, Any]],
        label: str,
    ) -> ToolResult:
        """格式化位置结果"""
        if not locations:
            return ToolResult.ok(f"No {label} found.")

        lines = [f"{label.capitalize()} ({len(locations)}):\n"]
        seen = set()

        for loc in locations[:20]:  # 限制数量
            uri = loc.get("uri", "")
            path = Path(uri.replace("file://", "")).name if uri else "unknown"
            rng = loc.get("range", {})
            start = rng.get("start", {})
            line = start.get("line", 0) + 1
            col = start.get("character", 0)

            key = f"{path}:{line}:{col}"
            if key in seen:
                continue
            seen.add(key)

            lines.append(f"  {path}:{line}:{col}")

        return ToolResult.ok("\n".join(lines))

    def _format_hover(self, result: Optional[Dict[str, Any]]) -> ToolResult:
        """格式化悬停结果"""
        if not result:
            return ToolResult.ok("No hover info available.")

        contents = result.get("contents", {})
        if isinstance(contents, str):
            return ToolResult.ok(contents)

        value = contents.get("value", str(contents))
        return ToolResult.ok(value)

    def _format_completions(self, items: List[Dict[str, Any]]) -> ToolResult:
        """格式化补全结果"""
        if not items:
            return ToolResult.ok("No completions available.")

        lines = [f"Completions ({len(items)}):\n"]
        for item in items[:20]:
            label = item.get("label", "")
            kind = item.get("kind", "")
            detail = item.get("detail", "")
            lines.append(f"  {label}  {detail}")

        return ToolResult.ok("\n".join(lines))
