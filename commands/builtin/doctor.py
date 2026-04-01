"""
DoctorCommand - 环境诊断命令

对应 Claude Code 源码: src/commands/doctor/

功能：
- 检查 Python 版本
- 检查 API key 配置
- 检查依赖包
- 检查目录权限
- 检查网络连通性
- 检查磁盘空间
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from commands.base import Command, CommandContext, CommandResult


class DoctorCommand(Command):
    """环境诊断"""

    name = "doctor"
    description = "Diagnose and verify installation"
    aliases = []
    usage = """/doctor
    Diagnose and verify your Claude Code installation and settings.
    
Checks:
  - Python version
  - API key configuration
  - Required dependencies
  - Directory permissions
  - Disk space
  - Network connectivity"""

    def __init__(self) -> None:
        self._checks: List[Tuple[str, callable]] = []

    async def execute(self, args: List[str], context: CommandContext) -> CommandResult:
        """执行诊断"""
        try:
            lines = ["\n=== Claude Code Doctor ===\n"]
            issues = []
            warnings = []
            
            # 运行所有检查
            checks = [
                ("Python Version", self._check_python),
                ("API Key", self._check_api_key),
                ("Dependencies", self._check_dependencies),
                ("Directories", self._check_directories),
                ("Disk Space", self._check_disk_space),
                ("Network", self._check_network),
            ]
            
            for name, check_fn in checks:
                ok, message, issue_type = check_fn()
                status = "✅" if ok else ("⚠️" if issue_type == "warning" else "❌")
                lines.append(f"{status} {name}")
                lines.append(f"   {message}")
                
                if not ok:
                    if issue_type == "error":
                        issues.append(f"{name}: {message}")
                    else:
                        warnings.append(f"{name}: {message}")
                
                lines.append("")
            
            # 总结
            if issues:
                lines.append("❌ Issues found:")
                for issue in issues:
                    lines.append(f"   - {issue}")
                lines.append("")
            
            if warnings:
                lines.append("⚠️  Warnings:")
                for warning in warnings:
                    lines.append(f"   - {warning}")
                lines.append("")
            
            if not issues:
                lines.append("✅ All checks passed!")
            else:
                lines.append("Please fix the issues above.")
            
            lines.append("")
            
            return CommandResult.ok("\n".join(lines))
        
        except Exception as e:
            return CommandResult.err(f"Doctor error: {e}")

    def _check_python(self) -> Tuple[bool, str, str]:
        """检查 Python 版本"""
        version = sys.version_info
        if version.major >= 3 and version.minor >= 10:
            return True, f"Python {version.major}.{version.minor}.{version.micro}", "info"
        else:
            return False, f"Python {version.major}.{version.minor} - requires 3.10+", "error"

    def _check_api_key(self) -> Tuple[bool, str, str]:
        """检查 API key"""
        key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
        if key:
            masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
            return True, f"API key configured: {masked}", "info"
        else:
            return False, "ANTHROPIC_API_KEY not set", "error"

    def _check_dependencies(self) -> Tuple[bool, str, str]:
        """检查依赖包"""
        required = ["anthropic"]
        optional = ["tiktoken", "tiktoken"]
        
        missing_required = []
        missing_optional = []
        
        for pkg in required:
            try:
                __import__(pkg)
            except ImportError:
                missing_required.append(pkg)
        
        for pkg in optional:
            try:
                __import__(pkg)
            except ImportError:
                missing_optional.append(pkg)
        
        if missing_required:
            return False, f"Missing required: {', '.join(missing_required)}", "error"
        
        if missing_optional:
            return True, f"Optional missing: {', '.join(missing_optional)} (tiktoken recommended)", "warning"
        
        return True, "All dependencies installed", "info"

    def _check_directories(self) -> Tuple[bool, str, str]:
        """检查目录"""
        dirs = [
            ("Home", Path.home()),
            ("Config", Path.home() / ".claude"),
            ("Memory", Path.home() / ".claude" / "memory"),
            ("Logs", Path.home() / ".claude" / "logs"),
        ]
        
        all_ok = True
        issues = []
        
        for name, path in dirs:
            if path.exists():
                if os.access(path, os.W_OK):
                    pass  # OK
                else:
                    issues.append(f"{name} ({path}) not writable")
                    all_ok = False
            else:
                try:
                    path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    issues.append(f"{name} ({path}): {e}")
                    all_ok = False
        
        if all_ok:
            return True, "All directories accessible", "info"
        else:
            return False, "; ".join(issues), "error"

    def _check_disk_space(self) -> Tuple[bool, str, str]:
        """检查磁盘空间"""
        try:
            import shutil
            total, used, free = shutil.disk_usage("/")
            
            # 转换为 GB
            total_gb = total / (1024**3)
            free_gb = free / (1024**3)
            
            if free_gb < 1:
                return False, f"Low disk space: {free_gb:.1f} GB free", "error"
            elif free_gb < 5:
                return True, f"Disk space: {free_gb:.1f} GB free ({total_gb:.1f} GB total)", "warning"
            else:
                return True, f"Disk space OK: {free_gb:.1f} GB free", "info"
        
        except Exception as e:
            return True, f"Could not check disk space: {e}", "warning"

    def _check_network(self) -> Tuple[bool, str, str]:
        """检查网络连通性"""
        try:
            import urllib.request
            req = urllib.request.Request(
                "https://api.anthropic.com",
                method="HEAD"
            )
            urllib.request.urlopen(req, timeout=5)
            return True, "api.anthropic.com reachable", "info"
        except Exception:
            return True, "api.anthropic.com not reachable (will work with API key)", "warning"
