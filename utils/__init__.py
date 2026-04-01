"""
Utils Module - 工具函数库

通用工具函数。
对应 Claude Code 源码: src/utils/*.ts
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

# ============================================================================
# 时间工具
# ============================================================================

def now_utc() -> datetime:
    """获取当前 UTC 时间"""
    return datetime.now(timezone.utc)


def now_iso() -> str:
    """获取当前 UTC 时间（ISO 格式）"""
    return datetime.now(timezone.utc).isoformat()


def now_timestamp() -> float:
    """获取当前时间戳（秒）"""
    return time.time()


def now_timestamp_ms() -> int:
    """获取当前时间戳（毫秒）"""
    return int(time.time() * 1000)


def format_duration(seconds: float) -> str:
    """格式化时长"""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"


def parse_duration(duration_str: str) -> Optional[float]:
    """
    解析时长字符串。
    
    Examples:
        "1h30m" -> 5400.0
        "30s" -> 30.0
        "100ms" -> 0.1
    """
    pattern = r"(\d+(?:\.\d+)?)([smh]|ms)"
    match = re.fullmatch(pattern, duration_str.lower())
    if not match:
        return None
    
    value = float(match.group(1))
    unit = match.group(2)
    
    if unit == "ms":
        return value / 1000
    elif unit == "s":
        return value
    elif unit == "m":
        return value * 60
    elif unit == "h":
        return value * 3600
    
    return None


# ============================================================================
# 字符串工具
# ============================================================================

T = TypeVar("T")


def truncate(s: str, max_length: int, suffix: str = "...") -> str:
    """截断字符串"""
    if len(s) <= max_length:
        return s
    return s[:max_length - len(suffix)] + suffix


def strip_ansi(text: str) -> str:
    """移除 ANSI 转义序列"""
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_pattern.sub("", text)


def slugify(text: str, max_length: int = 50) -> str:
    """转换为 URL 友好的 slug"""
    # 转小写，替换空格为横线
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    return truncate(slug, max_length, "")


def extract_code_blocks(text: str) -> List[Dict[str, str]]:
    """
    从文本中提取代码块。
    
    Returns:
        [{"language": "python", "code": "print('hello')"}, ...]
    """
    pattern = r"```(\w+)?\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    return [
        {"language": lang or "text", "code": code.strip()}
        for lang, code in matches
    ]


# ============================================================================
# 文件工具
# ============================================================================

def ensure_dir(path: Union[str, Path]) -> Path:
    """确保目录存在"""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_parent_dir(path: Union[str, Path]) -> Path:
    """确保父目录存在"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def read_json(path: Union[str, Path]) -> Any:
    """读取 JSON 文件"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Union[str, Path], data: Any, indent: int = 2) -> None:
    """写入 JSON 文件"""
    ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def file_hash(path: Union[str, Path], algorithm: str = "sha256") -> str:
    """计算文件哈希"""
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def file_size(path: Union[str, Path]) -> int:
    """获取文件大小（字节）"""
    return Path(path).stat().st_size


def format_size(size: int) -> str:
    """格式化文件大小"""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}PB"


# ============================================================================
# 加密/编码工具
# ============================================================================

def base64_encode(data: Union[str, bytes]) -> str:
    """Base64 编码"""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return base64.b64encode(data).decode("ascii")


def base64_decode(data: str) -> bytes:
    """Base64 解码"""
    return base64.b64decode(data)


def generate_id(prefix: str = "") -> str:
    """生成唯一 ID"""
    import uuid
    uid = uuid.uuid4().hex[:12]
    return f"{prefix}{uid}" if prefix else uid


def generate_token(length: int = 32) -> str:
    """生成随机令牌"""
    import secrets
    return secrets.token_urlsafe(length)


# ============================================================================
# 异步工具
# ============================================================================

async def run_in_executor(func: Callable[..., T], *args: Any) -> T:
    """在线程池中运行同步函数"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)


async def timeout_after(seconds: float, coro):
    """超时包装"""
    return await asyncio.wait_for(coro, timeout=seconds)


class AsyncBatch:
    """异步批处理器"""
    
    def __init__(
        self,
        max_concurrency: int = 5,
        max_queue: int = 100,
    ) -> None:
        self.max_concurrency = max_concurrency
        self.max_queue = max_queue
        self.semaphore = asyncio.Semaphore(max_concurrency)
    
    async def process(
        self,
        items: List[Any],
        handler: Callable[[Any], Any],
    ) -> List[Any]:
        """处理一批项目"""
        async def process_one(item):
            async with self.semaphore:
                return await handler(item)
        
        return await asyncio.gather(*[process_one(item) for item in items])


# ============================================================================
# 数据结构工具
# ============================================================================

def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """深度合并字典"""
    result = {}
    for d in dicts:
        for key, value in d.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = merge_dicts(result[key], value)
            else:
                result[key] = value
    return result


def group_by(items: List[T], key: Callable[[T], Any]) -> Dict[Any, List[T]]:
    """按键分组"""
    groups: Dict[Any, List[T]] = {}
    for item in items:
        k = key(item)
        if k not in groups:
            groups[k] = []
        groups[k].append(item)
    return groups


def deduplicate(items: List[T], key: Optional[Callable[[T], Any]] = None) -> List[T]:
    """去重"""
    if key is None:
        seen = set()
        result = []
        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result
    else:
        seen = set()
        result = []
        for item in items:
            k = key(item)
            if k not in seen:
                seen.add(k)
                result.append(item)
        return result


# ============================================================================
# 环境工具
# ============================================================================

def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """获取环境变量"""
    return os.environ.get(key, default)


def get_env_int(key: str, default: int = 0) -> int:
    """获取整数环境变量"""
    value = os.environ.get(key)
    if value:
        try:
            return int(value)
        except ValueError:
            pass
    return default


def get_env_bool(key: str, default: bool = False) -> bool:
    """获取布尔环境变量"""
    value = os.environ.get(key, "").lower()
    if value in ("true", "1", "yes", "on"):
        return True
    if value in ("false", "0", "no", "off"):
        return False
    return default


def expand_path(path: str) -> Path:
    """展开路径中的 ~ 和环境变量"""
    return Path(os.path.expanduser(os.path.expandvars(path)))


# ============================================================================
# 类型工具
# ============================================================================

def isinstance_safe(obj: Any, class_or_tuple: Any) -> bool:
    """安全 isinstance 检查（捕获异常）"""
    try:
        return isinstance(obj, class_or_tuple)
    except Exception:
        return False


def cast(obj: Any, target_type: T) -> T:
    """类型转换（仅做类型提示）"""
    return obj  # type: ignore


__all__ = [
    # 时间
    "now_utc",
    "now_iso",
    "now_timestamp",
    "now_timestamp_ms",
    "format_duration",
    "parse_duration",
    # 字符串
    "truncate",
    "strip_ansi",
    "slugify",
    "extract_code_blocks",
    # 文件
    "ensure_dir",
    "ensure_parent_dir",
    "read_json",
    "write_json",
    "file_hash",
    "file_size",
    "format_size",
    # 加密/编码
    "base64_encode",
    "base64_decode",
    "generate_id",
    "generate_token",
    # 异步
    "run_in_executor",
    "timeout_after",
    "AsyncBatch",
    # 数据结构
    "merge_dicts",
    "group_by",
    "deduplicate",
    # 环境
    "get_env",
    "get_env_int",
    "get_env_bool",
    "expand_path",
    # 类型
    "isinstance_safe",
    "cast",
]
