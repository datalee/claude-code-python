"""
Skill System - Skill 加载与执行系统

Skill 是可扩展的能力单元，格式兼容 OpenClaw SKILL.md 规范：
- SKILL.md: YAML frontmatter (name, description) + markdown body
- 支持从目录加载
- 支持 skill 匹配和执行

对应 Claude Code 源码: src/skill/*.ts
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# Skill 数据结构
# =============================================================================

@dataclass
class Skill:
    """
    Skill 定义。
    
    对应一个 SKILL.md 文件。
    """
    name: str                          # Skill 名称
    slug: str                          # 目录 slug
    description: str                   # 描述（用于匹配）
    content: str = ""                  # Markdown 内容（完整 prompt）
    triggers: List[str] = None         # 触发关键词
    version: str = "1.0.0"
    
    def __post_init__(self):
        if self.triggers is None:
            self.triggers = []


@dataclass
class SkillMatch:
    """Skill 匹配结果"""
    skill: Skill
    confidence: float  # 0.0 - 1.0
    reason: str


# =============================================================================
# Skill Loader - 从文件系统加载
# =============================================================================

class SkillLoader:
    """
    Skill 加载器。
    
    从 skills_dir 目录扫描并加载所有 SKILL.md 文件。
    """
    
    # SKILL.md 文件名
    SKILL_FILE = "SKILL.md"
    
    def __init__(self, skills_dir: Optional[str] = None):
        """
        初始化加载器。
        
        Args:
            skills_dir: Skills 目录路径，默认为 ~/.claude/skills/
        """
        if skills_dir:
            self.skills_dir = Path(skills_dir)
        else:
            # 默认目录
            self.skills_dir = Path.home() / ".claude" / "skills"
        
        self._skills: Dict[str, Skill] = {}
    
    def load_all(self) -> Dict[str, Skill]:
        """
        加载所有 skills。
        
        Returns:
            {slug: Skill} 字典
        """
        self._skills.clear()
        
        if not self.skills_dir.exists():
            return self._skills
        
        for item in self.skills_dir.iterdir():
            if not item.is_dir():
                continue
            
            skill_file = item / self.SKILL_FILE
            if not skill_file.exists():
                continue
            
            skill = self._load_skill_file(item.name, skill_file)
            if skill:
                self._skills[skill.slug] = skill
        
        return self._skills
    
    def _load_skill_file(self, slug: str, path: Path) -> Optional[Skill]:
        """
        加载单个 SKILL.md 文件。
        
        格式：
        ---
        name: skill-name
        description: "Description text"
        triggers: ["trigger1", "trigger2"]
        ---
        
        # Markdown content...
        """
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            return None
        
        # 解析 YAML frontmatter
        frontmatter, markdown = self._parse_frontmatter(content)
        
        if not frontmatter:
            return None
        
        name = frontmatter.get("name", slug)
        description = frontmatter.get("description", "")
        triggers = frontmatter.get("triggers", [])
        version = frontmatter.get("version", "1.0.0")
        
        return Skill(
            name=name,
            slug=slug,
            description=description,
            content=markdown,
            triggers=triggers if isinstance(triggers, list) else [],
            version=version,
        )
    
    def _parse_frontmatter(self, content: str) -> Tuple[Dict[str, Any], str]:
        """
        解析 YAML frontmatter。
        
        格式：
        ---
        key: value
        ---
        markdown content
        """
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        
        if not match:
            return {}, content
        
        import yaml
        try:
            frontmatter = yaml.safe_load(match.group(1)) or {}
        except Exception:
            frontmatter = {}
        
        markdown = match.group(2).strip()
        
        return frontmatter, markdown
    
    def get_skill(self, slug: str) -> Optional[Skill]:
        """获取单个 skill"""
        if not self._skills:
            self.load_all()
        return self._skills.get(slug)
    
    def list_skills(self) -> List[Skill]:
        """列出所有 skill"""
        if not self._skills:
            self.load_all()
        return list(self._skills.values())
    
    def match(self, query: str, threshold: float = 0.3) -> List[SkillMatch]:
        """
        根据 query 匹配最合适的 skill。
        
        匹配逻辑：
        1. 精确匹配 slug
        2. 模糊匹配 description
        3. 匹配 triggers
        
        Args:
            query: 用户查询
            threshold: 最低置信度阈值
            
        Returns:
            按置信度排序的匹配结果
        """
        if not self._skills:
            self.load_all()
        
        query_lower = query.lower()
        matches: List[SkillMatch] = []
        
        for skill in self._skills.values():
            confidence = 0.0
            reason = ""
            
            # 1. 精确匹配 slug
            if query_lower == skill.slug.lower():
                confidence = 1.0
                reason = "exact slug match"
            
            # 2. slug 包含 query
            elif query_lower in skill.slug.lower():
                confidence = 0.8
                reason = "slug contains query"
            
            # 3. description 包含 query
            elif query_lower in skill.description.lower():
                confidence = 0.6
                reason = "description contains query"
            
            # 4. 匹配 triggers
            else:
                for trigger in skill.triggers:
                    if trigger.lower() in query_lower:
                        confidence = 0.7
                        reason = f"matched trigger '{trigger}'"
                        break
            
            if confidence >= threshold:
                matches.append(SkillMatch(
                    skill=skill,
                    confidence=confidence,
                    reason=reason,
                ))
        
        # 按置信度排序
        matches.sort(key=lambda m: m.confidence, reverse=True)
        
        return matches


# =============================================================================
# Skill Runner - 执行 Skill
# =============================================================================

class SkillRunner:
    """
    Skill 执行器。
    
    负责 skill 的匹配和执行。
    """
    
    def __init__(self, loader: Optional[SkillLoader] = None):
        self.loader = loader or SkillLoader()
        self.loader.load_all()
    
    def find_skill(self, query: str) -> Optional[Skill]:
        """
        根据 query 找到最匹配的 skill。
        
        Args:
            query: 用户查询或 /skill-name 格式
            
        Returns:
            匹配的 Skill 或 None
        """
        # 直接 /skill-name 格式
        if query.startswith("/"):
            slug = query[1:].strip()
            return self.loader.get_skill(slug)
        
        # 模糊匹配
        matches = self.loader.match(query)
        if matches:
            return matches[0].skill
        
        return None
    
    def invoke(self, skill_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用 skill，返回要注入的 prompt。
        
        Args:
            skill_name: Skill slug 或 query
            context: 执行上下文
            
        Returns:
            {"prompt": "...", "skill": Skill}
        """
        skill = self.find_skill(skill_name)
        if not skill:
            return {"error": f"Skill not found: {skill_name}"}
        
        return {
            "prompt": skill.content,
            "skill": skill,
        }
    
    def list_all(self) -> List[Dict[str, str]]:
        """列出所有可用 skill"""
        return [
            {
                "slug": s.slug,
                "name": s.name,
                "description": s.description,
                "triggers": ", ".join(s.triggers) if s.triggers else "-",
            }
            for s in self.loader.list_skills()
        ]


# =============================================================================
# 全局实例
# =============================================================================

_loader: Optional[SkillLoader] = None
_runner: Optional[SkillRunner] = None


def get_skill_loader() -> SkillLoader:
    global _loader
    if _loader is None:
        _loader = SkillLoader()
        _loader.load_all()
    return _loader


def get_skill_runner() -> SkillRunner:
    global _runner
    if _runner is None:
        _runner = SkillRunner()
    return _runner


__all__ = [
    "Skill",
    "SkillMatch",
    "SkillLoader",
    "SkillRunner",
    "get_skill_loader",
    "get_skill_runner",
]
