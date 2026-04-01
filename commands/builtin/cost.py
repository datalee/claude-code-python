"""
CostCommand - 成本查看命令

对应 Claude Code 源码: src/commands/builtin/cost.ts
"""

from __future__ import annotations

from typing import List

from commands.base import Command, CommandContext, CommandResult


class CostCommand(Command):
    """查看 Token 消耗和成本"""

    name = "cost"
    description = "Show token usage and cost statistics"
    aliases = ["c", "usage"]
    usage = """/cost
    Show token usage and cost statistics since session start.

Displays:
  - Total API cost (USD)
  - Token breakdown by type (input, output, cache)
  - API call duration
  - Code changes (lines added/removed)"""

    async def execute(self, args: List[str], context: CommandContext) -> CommandResult:
        """执行成本查看命令"""
        if context.cost_tracker is None:
            return CommandResult.err("Cost tracker not available")

        try:
            tracker = context.cost_tracker
            
            # 获取成本报告
            if hasattr(tracker, 'format_total_cost'):
                report = tracker.format_total_cost()
            else:
                # 手动生成报告
                report = self._generate_report(tracker)
            
            return CommandResult.ok(report)
        
        except Exception as e:
            return CommandResult.err(f"Failed to get cost stats: {e}")

    def _generate_report(self, tracker) -> str:
        """生成成本报告"""
        lines = ["\n=== Cost Statistics ===", ""]
        
        # 总成本
        total_cost = getattr(tracker, 'total_cost', 0)
        lines.append(f"Total cost:          ${total_cost:.4f}")
        
        # API 耗时
        total_duration = getattr(tracker, 'total_api_duration_ms', 0)
        lines.append(f"Total API duration:  {total_duration/1000:.1f}s")
        
        # 代码变化
        lines_added = getattr(tracker, 'lines_added', 0)
        lines_removed = getattr(tracker, 'lines_removed', 0)
        lines.append(f"Code changes:        +{lines_added} lines, -{lines_removed} lines")
        
        # 按模型统计
        if hasattr(tracker, 'usage_by_model') and tracker.usage_by_model:
            lines.append("")
            lines.append("Usage by model:")
            for model, usage in tracker.usage_by_model.items():
                cost = getattr(usage, 'total_cost', 0)
                lines.append(f"  {model}: ${cost:.4f}")
        
        lines.append("")
        return "\n".join(lines)
