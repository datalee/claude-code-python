"""
Skill System - Skill 加载与执行系统

加载和执行外部 Skill。
对应 Claude Code 源码: src/skill/*.ts
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class Skill(ABC):
    """
    Skill 基类。

    Skill 是一种可扩展的能力封装，类似于插件。
    """

    name: str = ""
    description: str = ""
    version: str = "1.0.0"

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Any:
        """执行 Skill"""
        raise NotImplementedError


class SkillResult:
    """Skill 执行结果"""

    def __init__(
        self,
        success: bool,
        output: Any = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.success = success
        self.output = output
        self.error = error
        self.metadata = metadata or {}


class SkillContext:
    """
    Skill 执行上下文。

    包含 Skill 执行时所需的所有信息。
    """

    def __init__(
        self,
        workspace_path: str,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.workspace_path = Path(workspace_path)
        self.agent_id = agent_id
        self.session_id = session_id
        self.user_id = user_id
        self.metadata = metadata or {}
        self.variables: Dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self.variables.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.variables[key] = value


class SkillLoader:
    """
    Skill 加载器。

    从文件系统加载 Skill。
    """

    def __init__(self, skills_dir: Optional[str] = None) -> None:
        """
        初始化加载器。

        Args:
            skills_dir: Skill 目录路径
        """
        if skills_dir:
            self.skills_dir = Path(skills_dir)
        else:
            # 默认 ~/.claude_code/skills/
            self.skills_dir = Path.home() / ".claude_code" / "skills"

        self._skills: Dict[str, type] = {}

    def discover_skills(self) -> List[str]:
        """
        发现所有可用的 Skill。

        Returns:
            Skill 名称列表
        """
        discovered = []

        if not self.skills_dir.exists():
            return discovered

        for item in self.skills_dir.iterdir():
            if item.is_dir() and (item / "skill.py").exists():
                discovered.append(item.name)
                self._load_skill(item.name)

        return discovered

    def _load_skill(self, name: str) -> Optional[type]:
        """加载单个 Skill"""
        if name in self._skills:
            return self._skills[name]

        skill_path = self.skills_dir / name / "skill.py"
        if not skill_path.exists():
            return None

        try:
            # 动态导入模块
            spec = importlib.util.spec_from_file_location(f"skill_{name}", skill_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # 查找 Skill 类
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and issubclass(attr, Skill) and attr != Skill:
                        self._skills[name] = attr
                        return attr

        except Exception as e:
            print(f"Failed to load skill {name}: {e}")

        return None

    def get_skill(self, name: str) -> Optional[type]:
        """获取 Skill 类"""
        if name not in self._skills:
            self._load_skill(name)
        return self._skills.get(name)

    def list_skills(self) -> List[Dict[str, str]]:
        """列出所有已加载的 Skill"""
        return [
            {
                "name": name,
                "description": cls.description if hasattr(cls, 'description') else "",
                "version": cls.version if hasattr(cls, 'version') else "1.0.0",
            }
            for name, cls in self._skills.items()
        ]


class SkillRunner:
    """
    Skill 执行器。

    管理 Skill 的执行。
    """

    def __init__(self, loader: Optional[SkillLoader] = None) -> None:
        self.loader = loader or SkillLoader()
        self._instances: Dict[str, Skill] = {}

    async def run(
        self,
        skill_name: str,
        context: SkillContext,
        **kwargs: Any,
    ) -> SkillResult:
        """
        运行 Skill。

        Args:
            skill_name: Skill 名称
            context: 执行上下文
            **kwargs: Skill 特定的参数

        Returns:
            SkillResult
        """
        # 获取 Skill 类
        skill_cls = self.loader.get_skill(skill_name)
        if not skill_cls:
            return SkillResult(
                success=False,
                error=f"Skill not found: {skill_name}"
            )

        # 创建实例
        if skill_name not in self._instances:
            self._instances[skill_name] = skill_cls()

        skill = self._instances[skill_name]

        # 执行
        try:
            # 构建输入
            input_data = {**context.metadata, **kwargs}

            # 执行
            output = await skill.execute(input_data)

            return SkillResult(
                success=True,
                output=output,
            )

        except Exception as e:
            return SkillResult(
                success=False,
                error=str(e),
            )

    def list_skills(self) -> List[Dict[str, str]]:
        """列出所有可用的 Skill"""
        return self.loader.list_skills()


# =============================================================================
# 内置 Skill 示例
# =============================================================================

class HelloWorldSkill(Skill):
    """Hello World Skill 示例"""

    name = "hello_world"
    description = "A simple hello world skill"
    version = "1.0.0"

    async def execute(self, context: Dict[str, Any]) -> str:
        name = context.get("name", "World")
        return f"Hello, {name}!"


class FileWriterSkill(Skill):
    """文件写入 Skill"""

    name = "file_writer"
    description = "Write content to a file"
    version = "1.0.0"

    async def execute(self, context: Dict[str, Any]) -> str:
        file_path = context.get("path")
        content = context.get("content", "")

        if not file_path:
            raise ValueError("path is required")

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

        return f"Written to {file_path}"


class ShellSkill(Skill):
    """Shell 命令执行 Skill"""

    name = "shell"
    description = "Execute a shell command"
    version = "1.0.0"

    async def execute(self, context: Dict[str, Any]) -> str:
        command = context.get("command")
        if not command:
            raise ValueError("command is required")

        proc = await asyncio.create_subprocess_exec(
            *command.split() if isinstance(command, str) else command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        result = stdout.decode() if stdout else ""
        if stderr:
            result += "\n--- stderr ---\n" + stderr.decode()

        return result


# 注册内置 Skill
BUILTIN_SKILLS = {
    "hello_world": HelloWorldSkill,
    "file_writer": FileWriterSkill,
    "shell": ShellSkill,
}


def get_builtin_skill(name: str) -> Optional[type]:
    """获取内置 Skill"""
    return BUILTIN_SKILLS.get(name)
