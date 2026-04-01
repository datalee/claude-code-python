"""
ModelCommand - 切换模型命令

对应 Claude Code 源码: src/commands/builtin/model.ts
"""

from __future__ import annotations

from typing import List

from commands.base import Command, CommandContext, CommandResult


# 支持的模型列表
AVAILABLE_MODELS = {
    "sonnet": "claude-sonnet-4-20250514",
    "opus": "claude-opus-4-20250514",
    "haiku": "claude-haiku-4-20250514",
    "sonnet35": "claude-sonnet-3-5-20250514",
    "opus35": "claude-opus-3-5-20250514",
}

MODEL_DISPLAY_NAMES = {
    "claude-sonnet-4-20250514": "Claude Sonnet 4",
    "claude-opus-4-20250514": "Claude Opus 4",
    "claude-haiku-4-20250514": "Claude Haiku 4",
    "claude-sonnet-3-5-20250514": "Claude Sonnet 3.5",
    "claude-opus-3-5-20250514": "Claude Opus 3.5",
}


class ModelCommand(Command):
    """切换模型"""

    name = "model"
    description = "Switch or show current model"
    aliases = ["m"]
    usage = """/model [model_name]
    Show available models or switch to a different model.

Available models:
  sonnet, opus, haiku, sonnet35, opus35"""

    async def execute(self, args: List[str], context: CommandContext) -> CommandResult:
        """执行模型切换命令"""
        # 无参数 - 显示当前模型
        if not args:
            current = context.engine.config.model if context.engine else "unknown"
            display_name = MODEL_DISPLAY_NAMES.get(current, current)
            output = f"Current model: {display_name}"
            output += "\n\nAvailable models:"
            for short, full in AVAILABLE_MODELS.items():
                name = MODEL_DISPLAY_NAMES.get(full, full)
                output += f"\n  {short:<10} {name}"
            return CommandResult.ok(output)

        # 解析模型名称
        model_arg = args[0].lower()
        
        # 查找完整模型名
        if model_arg in AVAILABLE_MODELS:
            model_full = AVAILABLE_MODELS[model_arg]
        elif model_arg in MODEL_DISPLAY_NAMES:
            model_full = model_arg
        else:
            return CommandResult.err(
                f"Unknown model: {model_arg}\n"
                f"Available: {', '.join(AVAILABLE_MODELS.keys())}"
            )

        # 切换模型
        if context.engine:
            old_model = context.engine.config.model
            context.engine.config.model = model_full
            
            # 更新 AgentConfig
            if hasattr(context.engine, 'config'):
                context.engine.config.model = model_full
            
            output = f"Model switched: {MODEL_DISPLAY_NAMES.get(old_model, old_model)} -> {MODEL_DISPLAY_NAMES.get(model_full, model_full)}"
        else:
            output = f"Model would be switched to: {MODEL_DISPLAY_NAMES.get(model_full, model_full)}"
            output += "\n(No engine context available)"

        return CommandResult.ok(output)
