"""Updater Service - Version Check and Auto Update"""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


CURRENT_VERSION = "1.0.0"


@dataclass
class UpdateInfo:
    available: bool
    current_version: str
    latest_version: str
    release_notes: str = ""
    download_url: str = ""


class Updater:
    def __init__(self) -> None:
        self._check_url = "https://api.github.com/repos/datalee/claude-code-python/releases/latest"

    def get_current_version(self) -> str:
        return CURRENT_VERSION

    async def check_for_updates(self) -> UpdateInfo:
        try:
            import urllib.request
            req = urllib.request.Request(self._check_url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            latest = data.get("tag_name", "").lstrip("v")
            return UpdateInfo(True, CURRENT_VERSION, latest, data.get("body", ""), data.get("html_url", ""))
        except Exception as e:
            return UpdateInfo(False, CURRENT_VERSION, CURRENT_VERSION, f"Check failed: {e}")


_updater: Optional[Updater] = None


def get_updater() -> Updater:
    global _updater
    if _updater is None:
        _updater = Updater()
    return _updater


__all__ = ["UpdateInfo", "Updater", "get_updater"]
