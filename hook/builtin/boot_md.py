"""
BootMdHook - 启动钩子

在 Gateway 启动时运行 BOOT.md 文件。
对应 Claude Code 源码: 内置钩子
参考: OpenClaw boot-md hook
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from hook.base import Hook, HookConfig, HookResult
from hook.events import EventType, HookEvent


class BootMdHook(Hook):
    """
    启动钩子。
    
    在 Gateway 启动时（渠道启动后）执行 BOOT.md 文件。
    用于初始化环境、加载配置、执行启动任务等。
    
    触发时机：
    - gateway:startup - Gateway 启动时
    
    执行逻辑：
    1. 查找 BOOT.md 文件（工作空间根目录）
    2. 如果存在，读取并执行其中的命令
    3. 支持纯文本命令和 shebang 脚本
    """

    name = "boot-md"
    description = "Run BOOT.md on gateway startup"
    version = "1.0.0"

    def __init__(
        self,
        workspace_path: Optional[str] = None,
        boot_file: str = "BOOT.md",
        timeout_seconds: int = 30,
    ) -> None:
        """
        初始化启动钩子。
        
        Args:
            workspace_path: 工作空间路径
            boot_file: BOOT.md 文件名
            timeout_seconds: 执行超时时间（秒）
        """
        super().__init__()
        
        self.workspace_path = Path(workspace_path) if workspace_path else Path.cwd()
        self.boot_file = self.workspace_path / boot_file
        self.timeout_seconds = timeout_seconds
        
        self.config = HookConfig(
            enabled=True,
            async_execute=False,  # 同步执行，阻塞启动
            timeout_ms=timeout_seconds * 1000,
        )

    def get_events(self) -> List[EventType]:
        return [EventType.GATEWAY_STARTUP]

    async def handle(self, event: HookEvent) -> HookResult:
        """处理启动事件，执行 BOOT.md"""
        try:
            # 检查 BOOT.md 是否存在
            if not self.boot_file.exists():
                return HookResult.ok(output={"skipped": "BOOT.md not found"})
            
            # 读取内容
            content = self.boot_file.read_text(encoding="utf-8")
            
            if not content.strip():
                return HookResult.ok(output={"skipped": "BOOT.md is empty"})
            
            # 解析命令
            commands = self._parse_commands(content)
            
            if not commands:
                return HookResult.ok(output={"skipped": "No commands found in BOOT.md"})
            
            # 执行命令
            results = []
            for cmd in commands:
                result = await self._execute_command(cmd)
                results.append(result)
                
                # 如果命令失败，默认继续执行（除非是 critical）
                if not result["success"] and result.get("critical"):
                    break
            
            # 汇总结果
            success_count = sum(1 for r in results if r["success"])
            
            return HookResult.ok(output={
                "executed": len(commands),
                "success": success_count,
                "failed": len(commands) - success_count,
                "results": results,
            })
        
        except Exception as e:
            return HookResult.err(f"BootMdHook failed: {e}")

    def _parse_commands(self, content: str) -> List[Dict[str, Any]]:
        """
        解析 BOOT.md 内容为命令列表。
        
        支持格式：
        ```markdown
        # BOOT.md
        
        ## Init
        $ echo "Hello"
        $ cd scripts && ./setup.sh
        
        ## Cleanup
        # cleanup temporary files
        $ rm -rf /tmp/*.tmp
        ```
        
        Returns:
            命令列表，每个命令是一个 dict：
            {
                "section": "Init",  # 所属章节
                "command": "echo 'Hello'",  # 要执行的命令
                "critical": False,  # 是否关键命令
            }
        """
        commands = []
        current_section = "default"
        
        lines = content.split("\n")
        
        for line in lines:
            stripped = line.strip()
            
            # 跳过空行和注释（除了代码块标记）
            if not stripped or stripped.startswith("#"):
                # 检查是否是章节标题
                if stripped.startswith("##"):
                    current_section = stripped.lstrip("#").strip()
                continue
            
            # 检查是否是命令（以 $ 开头）
            if stripped.startswith("$"):
                command = stripped[1:].strip()  # 去掉 $ 前缀
                
                # 检查是否有 [critical] 标记
                critical = False
                if command.endswith("[critical]"):
                    critical = True
                    command = command[:-10].strip()
                
                commands.append({
                    "section": current_section,
                    "command": command,
                    "critical": critical,
                })
        
        return commands

    async def _execute_command(self, cmd_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行单个命令。
        
        Args:
            cmd_info: 命令信息字典
            
        Returns:
            执行结果
        """
        command = cmd_info["command"]
        section = cmd_info["section"]
        
        try:
            # 根据系统选择 shell
            if sys.platform == "win32":
                # Windows
                shell = ["cmd", "/c", command]
            else:
                # Unix-like
                shell = ["sh", "-c", command]
            
            # 执行命令
            process = await asyncio.create_subprocess_exec(
                *shell,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout_seconds,
            )
            
            success = process.returncode == 0
            
            return {
                "section": section,
                "command": command,
                "success": success,
                "returncode": process.returncode,
                "stdout": stdout.decode("utf-8", errors="replace") if stdout else "",
                "stderr": stderr.decode("utf-8", errors="replace") if stderr else "",
                "critical": cmd_info["critical"],
            }
        
        except asyncio.TimeoutError:
            return {
                "section": section,
                "command": command,
                "success": False,
                "error": f"Command timed out after {self.timeout_seconds}s",
                "critical": cmd_info["critical"],
            }
        
        except Exception as e:
            return {
                "section": section,
                "command": command,
                "success": False,
                "error": str(e),
                "critical": cmd_info["critical"],
            }
