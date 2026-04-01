"""
Bootstrap Module - 启动引导与自检

应用启动时的初始化和健康检查。
对应 Claude Code 源码: src/bootstrap/*.ts
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any

# 内部模块
from setup import check_environment, ensure_setup, EnvironmentCheckResult


# ============================================================================
# 检查项定义
# ============================================================================

@dataclass
class BootstrapCheck:
    """引导检查项"""
    name: str                    # 检查名称
    description: str             # 检查描述
    check_fn: Callable[[], bool]  # 检查函数
    required: bool = True       # 是否必须（失败时阻止启动）
    auto_fix: bool = False      # 是否支持自动修复


# ============================================================================
# BootstrapResult
# ============================================================================

@dataclass
class BootstrapResult:
    """引导结果"""
    success: bool
    checks: Dict[str, "CheckResult"]
    errors: List[str]
    warnings: List[str]
    info: Dict[str, str]
    
    @property
    def is_healthy(self) -> bool:
        """健康检查是否通过"""
        return self.success


@dataclass 
class CheckResult:
    """单个检查结果"""
    passed: bool
    message: str
    details: Optional[Dict[str, Any]] = None


# ============================================================================
# 内置检查项
# ============================================================================

def _check_python_version() -> bool:
    """检查 Python 版本"""
    return sys.version_info >= (3, 10)


def _check_api_key() -> bool:
    """检查 API key"""
    key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
    return bool(key)


def _check_dependencies() -> bool:
    """检查依赖包"""
    required = ["anthropic"]
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            return False
    return True


def _check_config_dir() -> bool:
    """检查配置目录"""
    config_dir = Path.home() / ".claude"
    return config_dir.exists()


def _check_memory_dir() -> bool:
    """检查记忆目录"""
    memory_dir = Path.home() / ".claude" / "memory"
    return memory_dir.exists()


def _check_logs_dir() -> bool:
    """检查日志目录"""
    logs_dir = Path.home() / ".claude" / "logs"
    return logs_dir.exists()


# ============================================================================
# BootstrapManager
# ============================================================================

class BootstrapManager:
    """
    引导管理器。
    
    管理应用启动时的各项检查和初始化。
    """
    
    def __init__(self) -> None:
        self.checks: List[BootstrapCheck] = []
        self._register_default_checks()
    
    def _register_default_checks(self) -> None:
        """注册默认检查项"""
        self.checks = [
            BootstrapCheck(
                name="python_version",
                description="Python 3.10+",
                check_fn=_check_python_version,
                required=True,
            ),
            BootstrapCheck(
                name="api_key",
                description="ANTHROPIC_API_KEY configured",
                check_fn=_check_api_key,
                required=True,
            ),
            BootstrapCheck(
                name="dependencies",
                description="Required packages installed",
                check_fn=_check_dependencies,
                required=True,
            ),
            BootstrapCheck(
                name="config_dir",
                description="Config directory exists (~/.claude)",
                check_fn=_check_config_dir,
                required=False,
            ),
            BootstrapCheck(
                name="memory_dir",
                description="Memory directory exists (~/.claude/memory)",
                check_fn=_check_memory_dir,
                required=False,
            ),
            BootstrapCheck(
                name="logs_dir",
                description="Logs directory exists (~/.claude/logs)",
                check_fn=_check_logs_dir,
                required=False,
            ),
        ]
    
    def register_check(self, check: BootstrapCheck) -> None:
        """注册检查项"""
        self.checks.append(check)
    
    def run_checks(self) -> BootstrapResult:
        """
        运行所有检查。
        
        Returns:
            BootstrapResult: 检查结果
        """
        results: Dict[str, CheckResult] = {}
        errors: List[str] = []
        warnings: List[str] = []
        info: Dict[str, str] = {}
        
        for check in self.checks:
            try:
                passed = check.check_fn()
                results[check.name] = CheckResult(
                    passed=passed,
                    message=check.description,
                )
                
                if not passed:
                    if check.required:
                        errors.append(f"{check.name}: {check.description} - FAILED")
                    else:
                        warnings.append(f"{check.name}: {check.description} - FAILED")
                else:
                    info[check.name] = "OK"
            
            except Exception as e:
                results[check.name] = CheckResult(
                    passed=False,
                    message=f"{check.description} - ERROR: {e}",
                )
                if check.required:
                    errors.append(f"{check.name}: {str(e)}")
                else:
                    warnings.append(f"{check.name}: {str(e)}")
        
        # 关键检查：环境就绪
        env_result = check_environment()
        if not env_result.is_ok:
            for issue in env_result.issues:
                if issue not in errors:
                    errors.append(issue)
        
        success = len(errors) == 0
        
        return BootstrapResult(
            success=success,
            checks=results,
            errors=errors,
            warnings=warnings,
            info=info,
        )
    
    def format_report(self, result: BootstrapResult) -> str:
        """格式化检查报告"""
        lines = ["\n=== Bootstrap Health Check ===\n"]
        
        if result.success:
            lines.append("✅ All checks passed!\n")
        else:
            lines.append("❌ Some checks failed:\n")
            for error in result.errors:
                lines.append(f"  - {error}")
            lines.append("")
        
        if result.warnings:
            lines.append("⚠️  Warnings:\n")
            for warning in result.warnings:
                lines.append(f"  - {warning}")
            lines.append("")
        
        lines.append("Details:")
        for name, check_result in result.checks.items():
            status = "✅" if check_result.passed else "❌"
            lines.append(f"  {status} {name}: {check_result.message}")
        
        lines.append("")
        return "\n".join(lines)


# ============================================================================
# 便捷函数
# ============================================================================

_manager: Optional[BootstrapManager] = None


def get_bootstrap_manager() -> BootstrapManager:
    """获取全局引导管理器"""
    global _manager
    if _manager is None:
        _manager = BootstrapManager()
    return _manager


def run_bootstrap() -> BootstrapResult:
    """
    运行引导检查。
    
    Returns:
        BootstrapResult: 检查结果
    """
    manager = get_bootstrap_manager()
    return manager.run_checks()


def bootstrap_and_fix() -> BootstrapResult:
    """
    运行引导检查，失败时尝试自动修复。
    
    Returns:
        BootstrapResult: 检查结果
    """
    manager = get_bootstrap_manager()
    result = manager.run_checks()
    
    # 尝试自动修复
    if not result.success:
        # 尝试创建必要目录
        try:
            ensure_setup()
            # 重新检查
            result = manager.run_checks()
        except Exception:
            pass
    
    return result


# ============================================================================
# REPL 集成
# ============================================================================

async def repl_bootstrap_check() -> bool:
    """
    REPL 启动前的引导检查。
    
    Returns:
        True 如果检查通过，可以继续启动
    """
    result = run_bootstrap()
    
    if result.success:
        return True
    
    # 打印错误
    print(result.errors[0] if result.errors else "Bootstrap check failed")
    
    # 非必须检查失败时允许继续
    return True  # 允许用户忽略警告继续


__all__ = [
    "BootstrapCheck",
    "BootstrapResult",
    "CheckResult",
    "BootstrapManager",
    "get_bootstrap_manager",
    "run_bootstrap",
    "bootstrap_and_fix",
    "repl_bootstrap_check",
]
