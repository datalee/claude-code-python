"""
Git Worktree Tools - Git 工作树工具

进入/退出 Git Worktree，实现隔离工作区。
对应 Claude Code 内置工具: EnterWorktreeTool, ExitWorktreeTool
"""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from tool.base import Tool, ToolResult, Permission, PermissionScope, PermissionMode


class EnterWorktreeTool(Tool):
    """
    Enter (create or checkout) a Git worktree.

    Git worktree allows you to work on multiple branches simultaneously
    in separate directories, without stashing or switching.

    示例：
        enter_worktree(
            branch="feature/new-feature",
            path="./worktrees/feature-new"
        )
    """

    name = "enter_worktree"
    description = "Create or enter a Git worktree for isolated branch work."
    permission = Permission(mode=PermissionMode.ASK, scope=PermissionScope.WRITE)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "branch": {
                    "type": "string",
                    "description": "Branch name to create/checkout",
                },
                "path": {
                    "type": "string",
                    "description": "Worktree directory path",
                },
                "create": {
                    "type": "boolean",
                    "description": "Create new branch if it doesn't exist",
                    "default": True,
                },
                "upstream": {
                    "type": "string",
                    "description": "Upstream branch (e.g., 'main' for new branch)",
                    "default": "HEAD",
                },
            },
            "required": ["branch", "path"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        branch = input_data["branch"]
        path = input_data["path"]
        create = input_data.get("create", True)
        upstream = input_data.get("upstream", "HEAD")

        try:
            worktree_path = Path(path).resolve()

            # 检查是否已经是 worktree
            result = await self._run_git(["worktree", "list", "--porcelain"])
            worktrees = self._parse_worktree_list(result)

            for wt in worktrees:
                if wt["path"] == str(worktree_path):
                    # 已存在，直接进入
                    return ToolResult.ok(
                        content=f"Already in worktree: {worktree_path}",
                        metadata={"path": str(worktree_path), "branch": branch}
                    )

            # 检查目录是否已存在
            if worktree_path.exists() and any(worktree_path.iterdir()):
                return ToolResult.err(f"Directory already exists and is not empty: {path}")

            # 获取 git repo 根目录
            repo_root = await self._get_repo_root()
            if not repo_root:
                return ToolResult.err("Not a git repository")

            # 如果 create=True 且分支不存在，创建新分支
            if create:
                check_branch = await self._run_git(["rev-parse", "--verify", f"refs/heads/{branch}"])
                if not check_branch.strip():
                    # 分支不存在，创建
                    create_result = await self._run_git(["checkout", "-b", branch, upstream])
                    if create_result.returncode != 0:
                        return ToolResult.err(f"Failed to create branch: {create_result.stderr}")

            # 创建 worktree
            result = await self._run_git(["worktree", "add", worktree_path, branch])

            if result.returncode != 0:
                return ToolResult.err(f"Failed to create worktree: {result.stderr}")

            return ToolResult.ok(
                content=f"Entered worktree: {worktree_path}\nBranch: {branch}",
                metadata={
                    "path": str(worktree_path),
                    "branch": branch,
                    "worktree_path": str(worktree_path)
                }
            )

        except Exception as e:
            return ToolResult.err(f"Enter worktree error: {e}")

    async def _get_repo_root(self) -> Optional[str]:
        """获取 git 仓库根目录"""
        result = await self._run_git(["rev-parse", "--show-toplevel"])
        if result.returncode == 0:
            return result.stdout.strip()
        return None

    async def _run_git(self, args: List[str]) -> asyncio.subprocess.Process:
        """运行 git 命令"""
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        proc.stdout_text = stdout.decode() if stdout else ""
        proc.stderr = stderr.decode() if stderr else ""
        return proc

    def _parse_worktree_list(self, result: asyncio.subprocess.Process) -> List[Dict[str, str]]:
        """解析 git worktree list 输出"""
        worktrees = []
        current = {}

        for line in result.stdout_text.split("\n"):
            line = line.strip()
            if not line:
                if current:
                    worktrees.append(current)
                    current = {}
                continue

            if line.startswith("worktree "):
                current["path"] = line[9:].strip('"')
            elif line.startswith("branch "):
                current["branch"] = line[8:].strip('"')

        if current:
            worktrees.append(current)

        return worktrees


class ExitWorktreeTool(Tool):
    """
    Exit and remove a Git worktree.

    Removes the worktree directory and optionally prunes the branch.

    示例：
        exit_worktree(
            path="./worktrees/feature-new",
            remove_branch=True
        )
    """

    name = "exit_worktree"
    description = "Exit and remove a Git worktree."
    permission = Permission(mode=PermissionMode.ASK, scope=PermissionScope.WRITE)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Worktree directory path to remove",
                },
                "remove_branch": {
                    "type": "boolean",
                    "description": "Also delete the branch associated with the worktree",
                    "default": False,
                },
                "force": {
                    "type": "boolean",
                    "description": "Force removal even if there are uncommitted changes",
                    "default": False,
                },
            },
            "required": ["path"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        path = input_data["path"]
        remove_branch = input_data.get("remove_branch", False)
        force = input_data.get("force", False)

        try:
            worktree_path = Path(path).resolve()

            # 检查是否是 worktree
            result = await self._run_git(["worktree", "list", "--porcelain"])
            worktrees = self._parse_worktree_list(result)

            worktree_info = None
            for wt in worktrees:
                if Path(wt.get("path", "")).resolve() == worktree_path:
                    worktree_info = wt
                    break

            if not worktree_info:
                return ToolResult.err(f"Not a worktree: {path}")

            branch = worktree_info.get("branch", "")

            # 移除 worktree
            args = ["worktree", "remove", worktree_path]
            if force:
                args.append("--force")

            result = await self._run_git(args)

            if result.returncode != 0:
                return ToolResult.err(f"Failed to remove worktree: {result.stderr}")

            # 删除分支
            if remove_branch and branch:
                # 检查分支是否还有其他 worktree
                await self._run_git(["worktree", "prune"])

                # 安全地删除分支
                del_result = await self._run_git(["branch", "-d", branch])
                if del_result.returncode != 0:
                    # 分支未合并，尝试强制删除
                    del_result = await self._run_git(["branch", "-D", branch])

            return ToolResult.ok(
                content=f"Removed worktree: {worktree_path}",
                metadata={"path": str(worktree_path), "branch": branch}
            )

        except Exception as e:
            return ToolResult.err(f"Exit worktree error: {e}")

    async def _run_git(self, args: List[str]) -> asyncio.subprocess.Process:
        """运行 git 命令"""
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        proc.stdout_text = stdout.decode() if stdout else ""
        proc.stderr = stderr.decode() if stderr else ""
        return proc

    def _parse_worktree_list(self, result: asyncio.subprocess.Process) -> List[Dict[str, str]]:
        """解析 git worktree list 输出"""
        worktrees = []
        current = {}

        for line in result.stdout_text.split("\n"):
            line = line.strip()
            if not line:
                if current:
                    worktrees.append(current)
                    current = {}
                continue

            if line.startswith("worktree "):
                current["path"] = line[9:].strip('"')
            elif line.startswith("branch "):
                current["branch"] = line[8:].strip('"')

        if current:
            worktrees.append(current)

        return worktrees


class ListWorktreesTool(Tool):
    """
    List all Git worktrees in the repository.

    示例：
        list_worktrees()
    """

    name = "list_worktrees"
    description = "List all Git worktrees in the repository."
    permission = Permission(mode=PermissionMode.AUTOMATIC, scope=PermissionScope.READ)

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        try:
            result = await self._run_git(["worktree", "list", "--porcelain"])

            if result.returncode != 0:
                return ToolResult.err(f"Failed to list worktrees: {result.stderr}")

            worktrees = self._parse_worktree_list(result)

            if not worktrees:
                return ToolResult.ok("No worktrees found.")

            lines = ["Git Worktrees:\n"]
            for wt in worktrees:
                path = wt.get("path", "unknown")
                branch = wt.get("branch", "detached")
                lines.append(f"- {path} ({branch})")

            return ToolResult.ok("\n".join(lines))

        except Exception as e:
            return ToolResult.err(f"List worktrees error: {e}")

    async def _run_git(self, args: List[str]) -> asyncio.subprocess.Process:
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        proc.stdout_text = stdout.decode() if stdout else ""
        proc.stderr = stderr.decode() if stderr else ""
        return proc

    def _parse_worktree_list(self, result: asyncio.subprocess.Process) -> List[Dict[str, str]]:
        worktrees = []
        current = {}

        for line in result.stdout_text.split("\n"):
            line = line.strip()
            if not line:
                if current:
                    worktrees.append(current)
                    current = {}
                continue

            if line.startswith("worktree "):
                current["path"] = line[9:].strip('"')
            elif line.startswith("branch "):
                current["branch"] = line[8:].strip('"')

        if current:
            worktrees.append(current)

        return worktrees
