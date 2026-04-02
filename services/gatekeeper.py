"""
Gatekeeper Service - Permission Gatekeeper

对应 Claude Code 源码: src/services/gatekeeper.ts

功能：
- 权限检查
- 操作审批
- 危险操作拦截
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class PermissionMode(Enum):
    """权限模式"""
    SAFE = "safe"
    ASK = "ask"
    AUTO = "auto"
    OFF = "off"


DANGEROUS_OPERATIONS: Set[str] = {
    "delete", "drop", "remove", "rm", "uninstall",
    "format", "shutdown", "reboot", "exec", "eval",
    "spawn", "kill", "chmod", "chown", "sudo",
}

DANGEROUS_EXTENSIONS: Set[str] = {
    ".exe", ".dll", ".so", ".dylib", ".bat",
    ".cmd", ".ps1", ".vbs", ".sh",
}


@dataclass
class GateDecision:
    """权限决定"""
    allowed: bool
    reason: str
    requires_approval: bool = False
    user_confirmed: bool = False


class Gatekeeper:
    """权限守卫"""

    def __init__(self, mode: PermissionMode = PermissionMode.SAFE) -> None:
        self.mode = mode
        self._approval_callback: Optional[Callable[[str], bool]] = None

    def set_mode(self, mode: PermissionMode) -> None:
        self.mode = mode

    def set_approval_callback(self, callback: Callable[[str], bool]) -> None:
        self._approval_callback = callback

    def check_file_operation(
        self,
        operation: str,
        file_path: str,
        file_content: Optional[str] = None,
    ) -> GateDecision:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in DANGEROUS_EXTENSIONS:
            return GateDecision(False, f"Disallowed extension: {ext}", True)

        if operation.lower() in DANGEROUS_OPERATIONS:
            return GateDecision(False, f"Dangerous operation: {operation}", True)

        if self.mode == PermissionMode.SAFE:
            if operation.lower() in ("write", "create", "delete"):
                return GateDecision(False, "SAFE mode: modifications not allowed", True)

        if self.mode == PermissionMode.ASK:
            return GateDecision(True, "ASK mode: requires confirmation", True)

        return GateDecision(True, "Allowed")

    def check_command(self, command: str, args: Optional[List[str]] = None) -> GateDecision:
        cmd_lower = command.lower()
        if cmd_lower in DANGEROUS_OPERATIONS:
            return GateDecision(False, f"Dangerous command: {command}", True)

        if args:
            for arg in args:
                if any(d in arg.lower() for d in ["rm -rf", "drop", "shutdown"]):
                    return GateDecision(False, f"Dangerous argument: {arg}", True)

        if self.mode == PermissionMode.ASK:
            return GateDecision(True, "ASK mode: requires confirmation", True)

        return GateDecision(True, "Allowed")


_gatekeeper: Optional[Gatekeeper] = None


def get_gatekeeper() -> Gatekeeper:
    global _gatekeeper
    if _gatekeeper is None:
        _gatekeeper = Gatekeeper()
    return _gatekeeper


__all__ = ["PermissionMode", "DANGEROUS_OPERATIONS", "DANGEROUS_EXTENSIONS",
           "GateDecision", "Gatekeeper", "get_gatekeeper"]
