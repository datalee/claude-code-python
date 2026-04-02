"""
Entrypoints Module - Application Entry Points

应用入口点，处理初始化和启动逻辑。
对应 Claude Code 源码: src/entrypoints/*.ts

功能：
- CLI 入口点
- REPL 入口点
- 服务器模式入口点
- 配置初始化
- 环境检查
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("entrypoint")


class Entrypoint:
    """
    入口点基类。
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.parser = argparse.ArgumentParser(prog=name)

    def add_common_args(self) -> None:
        """添加通用参数"""
        self.parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
        self.parser.add_argument("--version", action="version", version="1.0.0")
        self.parser.add_argument("--config", type=str, help="Config file path")

    async def run(self, args: argparse.Namespace) -> int:
        """运行入口点"""
        raise NotImplementedError


class REPLEntrypoint(Entrypoint):
    """
    REPL 入口点。
    """

    def __init__(self) -> None:
        super().__init__("claude-code")
        self.add_common_args()
        self.parser.add_argument("--model", type=str, help="Model to use")
        self.parser.add_argument("--permission-mode", type=str, choices=["safe", "ask", "auto"], default="safe")

    async def run(self, args: argparse.Namespace) -> int:
        """运行 REPL"""
        logger.info("Starting Claude Code REPL...")

        # 检查环境
        if not self._check_environment():
            return 1

        # 加载配置
        config = self._load_config(args)

        # 启动 REPL
        try:
            from agent.repl import REPL
            from agent.query_engine import QueryEngine, AgentConfig

            config_obj = AgentConfig(
                model=args.model or config.get("model", "claude-sonnet-4-20250514"),
                permission_mode=args.permission_mode,
            )

            engine = QueryEngine(config=config_obj)
            repl = REPL(query_engine=engine)

            await repl.run()
            return 0

        except Exception as e:
            logger.error(f"REPL error: {e}")
            return 1

    def _check_environment(self) -> bool:
        """检查环境"""
        # 检查 Python 版本
        if sys.version_info < (3, 10):
            logger.error("Python 3.10+ required")
            return False

        # 检查 API key
        api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set")

        return True

    def _load_config(self, args: argparse.Namespace) -> Dict[str, Any]:
        """加载配置"""
        config_file = args.config or str(Path.home() / ".claude" / "config.json")

        if os.path.exists(config_file):
            import json
            with open(config_file) as f:
                return json.load(f)

        return {}


class ServerEntrypoint(Entrypoint):
    """
    服务器模式入口点。
    """

    def __init__(self) -> None:
        super().__init__("claude-code-server")
        self.add_common_args()
        self.parser.add_argument("--host", type=str, default="127.0.0.1")
        self.parser.add_argument("--port", type=int, default=8765)
        self.parser.add_argument("--mode", type=str, choices=["tcp", "http", "websocket"], default="tcp")

    async def run(self, args: argparse.Namespace) -> int:
        """运行服务器"""
        logger.info(f"Starting Claude Code Server on {args.host}:{args.port}...")

        try:
            from server import TCPServer, HTTPServer, WebSocketServer

            if args.mode == "tcp":
                server = TCPServer(host=args.host, port=args.port)
            elif args.mode == "http":
                server = HTTPServer(host=args.host, port=args.port)
            else:
                server = WebSocketServer(host=args.host, port=args.port)

            await server.start()

        except KeyboardInterrupt:
            logger.info("Server interrupted")
            return 0
        except Exception as e:
            logger.error(f"Server error: {e}")
            return 1

        return 0


class AgentEntrypoint(Entrypoint):
    """
    静默 Agent 模式入口点。
    """

    def __init__(self) -> None:
        super().__init__("claude-code-agent")
        self.add_common_args()
        self.parser.add_argument("--session", type=str, required=True, help="Session ID")
        self.parser.add_argument("prompt", type=str, help="Prompt to execute")

    async def run(self, args: argparse.Namespace) -> int:
        """运行 Agent"""
        logger.info(f"Running agent in session {args.session}...")

        try:
            from agent.query_engine import QueryEngine, AgentConfig

            config = AgentConfig(model="claude-sonnet-4-20250514")
            engine = QueryEngine(config=config)

            # 执行单个提示
            result = await engine.query(args.prompt)
            print(result)

            return 0

        except Exception as e:
            logger.error(f"Agent error: {e}")
            return 1


def main() -> int:
    """主入口点"""
    parser = argparse.ArgumentParser(description="Claude Code Python")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # REPL 命令
    repl_parser = subparsers.add_parser("repl", help="Start REPL")
    repl_parser.add_argument("--model", type=str)
    repl_parser.add_argument("--permission-mode", type=str, choices=["safe", "ask", "auto"], default="safe")

    # 服务器命令
    server_parser = subparsers.add_parser("server", help="Start server")
    server_parser.add_argument("--host", type=str, default="127.0.0.1")
    server_parser.add_argument("--port", type=int, default=8765)
    server_parser.add_argument("--mode", type=str, choices=["tcp", "http", "websocket"], default="tcp")

    # Agent 命令
    agent_parser = subparsers.add_parser("agent", help="Run agent")
    agent_parser.add_argument("--session", type=str, required=True)
    agent_parser.add_argument("prompt", type=str)

    args = parser.parse_args()

    if args.command == "repl":
        entrypoint = REPLEntrypoint()
        entrypoint.parser = parser
        return asyncio.run(entrypoint.run(args))

    elif args.command == "server":
        entrypoint = ServerEntrypoint()
        entrypoint.parser = parser
        return asyncio.run(entrypoint.run(args))

    elif args.command == "agent":
        entrypoint = AgentEntrypoint()
        entrypoint.parser = parser
        return asyncio.run(entrypoint.run(args))

    else:
        # 默认启动 REPL
        entrypoint = REPLEntrypoint()
        return asyncio.run(entrypoint.run(argparse.Namespace(
            model=None,
            permission_mode="safe",
            verbose=False,
            config=None,
        )))


if __name__ == "__main__":
    sys.exit(main())
