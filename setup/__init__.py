"""
Setup Module - 首次运行引导

首次运行时检查环境、配置 API key、初始化目录结构。
对应 Claude Code 源码: src/setup.ts
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

# 当前版本
__version__ = "1.0.0"


def check_environment() -> "EnvironmentCheckResult":
    """
    检查运行环境。
    
    Returns:
        EnvironmentCheckResult: 检查结果
    """
    issues: List[str] = []
    warnings: List[str] = []
    info: Dict[str, str] = {}
    
    # Python 版本
    py_version = sys.version_info
    if py_version.major < 3 or (py_version.major == 3 and py_version.minor < 10):
        issues.append(f"Python 3.10+ required, found {py_version.major}.{py_version.minor}")
    else:
        info["python"] = f"{py_version.major}.{py_version.minor}.{py_version.micro}"
    
    # API Key 检查
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
    if api_key:
        info["api_key"] = "***" + api_key[-4:] if len(api_key) > 4 else "***"
    else:
        warnings.append("ANTHROPIC_API_KEY not set")
    
    # 必要依赖检查
    required_packages = ["anthropic", "tiktoken"]
    missing = []
    for pkg in required_packages:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    
    if missing:
        issues.append(f"Missing packages: {', '.join(missing)}")
    
    # 可选依赖
    optional_packages = {
        "typer": "CLI framework",
        "readline": "Enhanced input (built-in)",
    }
    for pkg, desc in optional_packages.items():
        try:
            __import__(pkg)
            info[f"opt_{pkg}"] = "✓"
        except ImportError:
            warnings.append(f"Optional package not found: {pkg} ({desc})")
    
    # 目录检查
    home = Path.home()
    claude_dir = home / ".claude"
    memory_dir = claude_dir / "memory"
    
    if claude_dir.exists():
        info["config_dir"] = str(claude_dir)
    else:
        warnings.append(f"Config dir not found: {claude_dir} (will be created on first run)")
    
    # 平台信息
    info["platform"] = sys.platform
    info["cwd"] = os.getcwd()
    
    return EnvironmentCheckResult(
        issues=issues,
        warnings=warnings,
        info=info,
    )


class EnvironmentCheckResult:
    """环境检查结果"""
    
    def __init__(
        self,
        issues: List[str],
        warnings: List[str],
        info: Dict[str, str],
    ) -> None:
        self.issues = issues
        self.warnings = warnings
        self.info = info
    
    @property
    def is_ok(self) -> bool:
        """环境是否就绪"""
        return len(self.issues) == 0
    
    def format_report(self) -> str:
        """格式化检查报告"""
        lines = ["\n=== Environment Check ===\n"]
        
        if self.is_ok:
            lines.append("✅ All checks passed!\n")
        else:
            lines.append("❌ Issues found:\n")
            for issue in self.issues:
                lines.append(f"  - {issue}")
            lines.append("")
        
        if self.warnings:
            lines.append("⚠️  Warnings:\n")
            for warning in self.warnings:
                lines.append(f"  - {warning}")
            lines.append("")
        
        if self.info:
            lines.append("Info:\n")
            for key, value in self.info.items():
                lines.append(f"  {key}: {value}")
            lines.append("")
        
        return "\n".join(lines)


def setup_config_dir() -> Path:
    """
    创建配置目录结构。
    
    目录结构：
    ~/.claude/
    ├── config.json      # 用户配置
    ├── memory/          # 记忆目录
    │   ├── .index.md    # 记忆索引
    │   └──日记/         # 日记记忆
    └── logs/            # 日志目录
    """
    home = Path.home()
    claude_dir = home / ".claude"
    memory_dir = claude_dir / "memory"
    logs_dir = claude_dir / "logs"
    
    # 创建目录
    claude_dir.mkdir(exist_ok=True)
    memory_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)
    
    # 创建记忆索引
    index_file = memory_dir / ".index.md"
    if not index_file.exists():
        index_file.write_text(
            "# Claude Code Memory Index\n\n"
            "This directory contains your memory files.\n\n"
            "## Memory Types\n\n"
            "- `日记/` - Daily journal entries\n"
            "- `长期/` - Long-term memories\n"
            "- `user/` - User preferences and context\n"
            "- `project/` - Project-specific memories\n\n"
            "## Adding Memories\n\n"
            "Create a `.md` file with frontmatter:\n"
            "```yaml\n"
            "---\n"
            "name: Memory name\n"
            "description: What this memory contains\n"
            "type: user|project|reference\n"
            "tags: [tag1, tag2]\n"
            "created: 2024-01-01\n"
            "---\n"
            "```\n"
        )
    
    # 创建日记目录
    diary_dir = memory_dir / "日记"
    diary_dir.mkdir(exist_ok=True)
    
    # 创建长期记忆目录
    longterm_dir = memory_dir / "长期"
    longterm_dir.mkdir(exist_ok=True)
    
    return claude_dir


def get_default_config() -> dict:
    """获取默认配置"""
    return {
        "version": __version__,
        "model": "claude-sonnet-4-20250514",
        "permission_mode": "safe",
        "memory_enabled": True,
        "hooks_enabled": True,
        "auto_compact": True,
        "compact_threshold_tokens": 100000,
        "max_tokens": 4096,
        "temperature": 1.0,
    }


def setup_config_file(config_path: Optional[Path] = None) -> Path:
    """
    创建配置文件。
    
    Args:
        config_path: 配置文件路径，默认 ~/.claude/config.json
        
    Returns:
        配置文件路径
    """
    if config_path is None:
        config_path = Path.home() / ".claude" / "config.json"
    
    # 确保目录存在
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 如果文件已存在，不覆盖
    if config_path.exists():
        return config_path
    
    # 写入默认配置
    import json
    config_path.write_text(json.dumps(get_default_config(), indent=2))
    
    return config_path


def run_setup_wizard() -> "SetupResult":
    """
    运行设置向导。
    
    交互式引导用户完成首次配置。
    
    Returns:
        SetupResult: 设置结果
    """
    print("\n" + "=" * 50)
    print("  Claude Code Python - Setup Wizard")
    print("=" * 50)
    print()
    
    results: List[str] = []
    
    # 1. 环境检查
    print("1. Checking environment...")
    env_result = check_environment()
    print(env_result.format_report())
    results.append(f"Environment check: {'PASS' if env_result.is_ok else 'FAIL'}")
    
    if not env_result.is_ok:
        print("❌ Cannot proceed - please fix the issues above first.")
        return SetupResult(
            success=False,
            results=results,
            errors=env_result.issues,
        )
    
    # 2. 创建目录
    print("2. Setting up directories...")
    try:
        config_dir = setup_config_dir()
        print(f"   ✅ Config directory: {config_dir}")
        results.append(f"Config dir: {config_dir}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return SetupResult(success=False, results=results, errors=[str(e)])
    
    # 3. 创建配置
    print("3. Creating configuration...")
    try:
        config_path = setup_config_file()
        print(f"   ✅ Config file: {config_path}")
        results.append(f"Config file: {config_path}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return SetupResult(success=False, results=results, errors=[str(e)])
    
    # 完成
    print()
    print("=" * 50)
    print("  ✅ Setup complete!")
    print("=" * 50)
    print()
    print("Next steps:")
    print("  1. Set your API key:")
    print("     export ANTHROPIC_API_KEY=your_key_here")
    print("  2. Run Claude Code:")
    print("     python -m claude_code.main repl")
    print()
    
    return SetupResult(success=True, results=results)


class SetupResult:
    """设置结果"""
    
    def __init__(
        self,
        success: bool,
        results: List[str],
        errors: Optional[List[str]] = None,
    ) -> None:
        self.success = success
        self.results = results
        self.errors = errors or []


# 便捷函数
def ensure_setup() -> bool:
    """
    确保环境已设置。
    如果未设置，运行设置向导。
    
    Returns:
        True 如果设置成功
    """
    env = check_environment()
    if env.is_ok:
        # 确保目录存在
        try:
            setup_config_dir()
            setup_config_file()
            return True
        except Exception:
            return False
    else:
        return False


__all__ = [
    "check_environment",
    "EnvironmentCheckResult",
    "setup_config_dir",
    "setup_config_file",
    "get_default_config",
    "run_setup_wizard",
    "SetupResult",
    "ensure_setup",
]
