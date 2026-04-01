"""
Screens Module - REPL 富文本屏幕

提供 REPL 的富文本输出界面。
对应 Claude Code 源码: src/screens/*.ts

功能：
- 终端富文本渲染（颜色、样式）
- 分页显示
- 进度条
- 表格输出
- 代码高亮
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

# ============================================================================
# 颜色和样式
# ============================================================================

class Style:
    """文本样式"""
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"


class Color:
    """颜色"""
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    RESET = "\033[39m"
    
    # Bright colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


# 组合颜色和样式
def c(text: str, color: str) -> str:
    """添加颜色"""
    return f"{color}{text}{Color.RESET}"


def s(text: str, style: str) -> str:
    """添加样式"""
    return f"{style}{text}{Style.RESET}"


def cs(text: str, color: str, style: str = "") -> str:
    """添加颜色和样式"""
    return f"{style}{color}{text}{Color.RESET}{Style.RESET}"


# ============================================================================
# 屏幕渲染器
# ============================================================================

class ScreenRenderer:
    """
    屏幕渲染器。
    
    提供各种格式化输出的方法。
    """
    
    def __init__(self, output: Optional[Any] = None) -> None:
        self.output = output or sys.stdout
    
    def _write(self, text: str) -> None:
        """写入输出"""
        print(text, file=self.output, end="")
    
    def _write_line(self, text: str = "") -> None:
        """写入一行"""
        print(text, file=self.output)
    
    # =========================================================================
    # 基本元素
    # =========================================================================
    
    def clear(self) -> None:
        """清屏"""
        self._write("\033[2J\033[H")
    
    def clear_line(self) -> None:
        """清当前行"""
        self._write("\033[2K")
    
    def cursor_up(self, n: int = 1) -> None:
        """光标上移"""
        self._write(f"\033[{n}A")
    
    def cursor_down(self, n: int = 1) -> None:
        """光标下移"""
        self._write(f"\033[{n}B")
    
    def cursor_right(self, n: int = 1) -> None:
        """光标右移"""
        self._write(f"\033[{n}C")
    
    def cursor_left(self, n: int = 1) -> None:
        """光标左移"""
        self._write(f"\033[{n}D")
    
    def cursor_home(self) -> None:
        """光标归位"""
        self._write("\033[H")
    
    def save_cursor(self) -> None:
        """保存光标位置"""
        self._write("\033[s")
    
    def restore_cursor(self) -> None:
        """恢复光标位置"""
        self._write("\033[u")
    
    # =========================================================================
    # 标题和分隔线
    # =========================================================================
    
    def title(self, text: str, width: Optional[int] = None) -> None:
        """打印标题"""
        if width is None:
            width = self._terminal_width()
        
        pad = max(0, (width - len(text) - 4) // 2)
        line = "=" * width
        self._write_line(cs(f"{' ' * pad}[ {text} ]{' ' * pad}", Color.CYAN, Style.BOLD))
    
    def section(self, text: str, width: Optional[int] = None) -> None:
        """打印章节标题"""
        if width is None:
            width = self._terminal_width()
        
        self._write_line()
        self._write_line(cs(f"  {text}", Color.BLUE, Style.BOLD))
        self._write_line(c("  " + "─" * min(len(text), width - 4), Color.BLUE))
    
    def divider(self, char: str = "─", width: Optional[int] = None) -> None:
        """打印分隔线"""
        if width is None:
            width = self._terminal_width()
        self._write_line(c(char * width, Color.BLUE))
    
    def spacer(self) -> None:
        """打印空行"""
        self._write_line()
    
    # =========================================================================
    # 列表
    # =========================================================================
    
    def bullet_list(self, items: List[str], indent: int = 2) -> None:
        """打印项目列表"""
        bullet = c("•", Color.CYAN)
        for item in items:
            self._write_line(f"{' ' * indent}{bullet} {item}")
    
    def numbered_list(self, items: List[str], start: int = 1, indent: int = 2) -> None:
        """打印编号列表"""
        for i, item in enumerate(items, start):
            num = c(f"{i}.", Color.GREEN)
            self._write_line(f"{' ' * indent}{num} {item}")
    
    # =========================================================================
    # 表格
    # =========================================================================
    
    def table(
        self,
        headers: List[str],
        rows: List[List[str]],
        widths: Optional[List[int]] = None,
    ) -> None:
        """
        打印表格。
        
        Args:
            headers: 表头
            rows: 数据行
            widths: 每列宽度
        """
        if not rows:
            return
        
        # 计算列宽
        if widths is None:
            col_count = len(headers)
            max_width = self._terminal_width()
            min_width = 10
            available = max_width - col_count * 3 - 2  # 边框和间距
            base_width = available // col_count
            widths = [base_width] * col_count
        
        # 表头
        self._write(c("┌", Color.BLUE))
        for i, header in enumerate(headers):
            self._write(c("─" * (widths[i] + 2), Color.BLUE))
            if i < len(headers) - 1:
                self._write(c("┬", Color.BLUE))
        self._write_line(c("┐", Color.BLUE))
        
        # 表头内容
        self._write(c("│", Color.BLUE))
        for i, header in enumerate(headers):
            self._write(f" {cs(header[:widths[i]], Color.CYAN, Style.BOLD):<{widths[i]}} ")
            self._write(c("│", Color.BLUE))
        self._write_line()
        
        # 分隔线
        self._write(c("├", Color.BLUE))
        for i in range(len(headers)):
            self._write(c("─" * (widths[i] + 2), Color.BLUE))
            if i < len(headers) - 1:
                self._write(c("┼", Color.BLUE))
        self._write_line(c("┤", Color.BLUE))
        
        # 数据行
        for row in rows:
            self._write(c("│", Color.BLUE))
            for i, cell in enumerate(row):
                self._write(f" {cell[:widths[i]]:<{widths[i]}} ")
                self._write(c("│", Color.BLUE))
            self._write_line()
        
        # 底边框
        self._write(c("└", Color.BLUE))
        for i in range(len(headers)):
            self._write(c("─" * (widths[i] + 2), Color.BLUE))
            if i < len(headers) - 1:
                self._write(c("┴", Color.BLUE))
        self._write_line(c("┘", Color.BLUE))
    
    # =========================================================================
    # 进度条
    # =========================================================================
    
    def progress_bar(
        self,
        current: float,
        total: float,
        width: Optional[int] = None,
        prefix: str = "",
        show_percent: bool = True,
    ) -> None:
        """
        打印进度条。
        
        Args:
            current: 当前进度
            total: 总数
            width: 进度条宽度
            prefix: 前缀文本
            show_percent: 是否显示百分比
        """
        if width is None:
            width = max(20, self._terminal_width() - 40)
        
        percent = min(100, (current / total * 100)) if total > 0 else 0
        filled = int(width * current / total) if total > 0 else 0
        empty = width - filled
        
        bar = c("█" * filled, Color.GREEN) + c("░" * empty, Color.WHITE)
        percent_str = f"{percent:.1f}%"
        
        line = f"\r{prefix} │{bar}│ {percent_str}"
        if show_percent:
            self._write(line)
        else:
            self._write(f"\r{prefix} │{bar}│")
    
    def progress_complete(self, text: str = "Done!") -> None:
        """进度完成"""
        self._write_line()
        self._write_line(cs(f"  ✓ {text}", Color.GREEN, Style.BOLD))
    
    # =========================================================================
    # 状态显示
    # =========================================================================
    
    def status_ok(self, text: str) -> None:
        """成功状态"""
        self._write_line(cs(f"  ✓ {text}", Color.GREEN))
    
    def status_warn(self, text: str) -> None:
        """警告状态"""
        self._write_line(cs(f"  ⚠ {text}", Color.YELLOW))
    
    def status_error(self, text: str) -> None:
        """错误状态"""
        self._write_line(cs(f"  ✗ {text}", Color.RED))
    
    def status_info(self, text: str) -> None:
        """信息状态"""
        self._write_line(cs(f"  ℹ {text}", Color.CYAN))
    
    # =========================================================================
    # 代码显示
    # =========================================================================
    
    def code_block(self, code: str, language: str = "", max_lines: Optional[int] = None) -> None:
        """
        显示代码块。
        
        Args:
            code: 代码内容
            language: 语言
            max_lines: 最大行数（超过则截断）
        """
        lines = code.split("\n")
        if max_lines and len(lines) > max_lines:
            lines = lines[:max_lines] + [cs("  ... (truncated)", Color.YELLOW)]
        
        # 边框
        lang_tag = f" {language} " if language else " "
        top = c("┌", Color.BLUE) + c("─" * 2, Color.BLUE) + c(lang_tag, Color.CYAN) + c("─" * (40 - len(language)), Color.BLUE)
        self._write_line(top)
        
        for line in lines:
            self._write_line(f"{c('│', Color.BLUE)} {line}")
        
        self._write_line(c("└" + "─" * 50, Color.BLUE))
    
    # =========================================================================
    # 帮助信息
    # =========================================================================
    
    def help_command(self, cmd: str, desc: str, indent: int = 2) -> None:
        """显示命令帮助"""
        cmd_formatted = cs(f"/{cmd}", Color.CYAN, Style.BOLD)
        self._write_line(f"{' ' * indent}{cmd_formatted:<20} {desc}")
    
    def help_section(self, title: str) -> None:
        """显示帮助章节"""
        self._write_line()
        self._write_line(cs(f"  {title}", Color.BLUE, Style.BOLD))
        self._write_line(c("  " + "─" * 30, Color.BLUE))
    
    # =========================================================================
    # 工具方法
    # =========================================================================
    
    def _terminal_width(self) -> int:
        """获取终端宽度"""
        try:
            import shutil
            return shutil.get_terminal_size().columns
        except Exception:
            return 80
    
    def pager(
        self,
        items: List[str],
        per_page: int = 20,
        formatter: Optional[Callable[[str], str]] = None,
    ) -> None:
        """
        分页显示。
        
        Args:
            items: 要显示的项目列表
            per_page: 每页数量
            formatter: 格式化函数
        """
        total_pages = (len(items) + per_page - 1) // per_page
        page = 0
        
        while True:
            start = page * per_page
            end = min(start + per_page, len(items))
            
            # 显示当前页
            for item in items[start:end]:
                text = formatter(item) if formatter else item
                self._write_line(text)
            
            # 分页提示
            self._write_line()
            if total_pages > 1:
                self._write_line(cs(f"  Page {page + 1}/{total_pages}  (↑↓ navigate, q quit)", Color.DIM))
            
            # 获取输入
            try:
                key = input() or "q"
                if key.lower() in ("q", "quit", "exit"):
                    break
                elif key in ("n", "next", "down", "j"):
                    if page < total_pages - 1:
                        page += 1
                elif key in ("p", "prev", "up", "k"):
                    if page > 0:
                        page -= 1
            except (EOFError, KeyboardInterrupt):
                break
            
            # 清屏重绘
            self._write("\033[2J\033[H")


# ============================================================================
# 全局实例
# ============================================================================

_renderer: Optional[ScreenRenderer] = None


def get_renderer() -> ScreenRenderer:
    """获取全局屏幕渲染器"""
    global _renderer
    if _renderer is None:
        _renderer = ScreenRenderer()
    return _renderer


__all__ = [
    # 样式和颜色
    "Style",
    "Color",
    "c",
    "s",
    "cs",
    # 渲染器
    "ScreenRenderer",
    "get_renderer",
]
