# Claude Code Python

A minimal Python reference implementation of [Claude Code](https://github.com/instructkr/claude-code) — an AI coding agent CLI tool.

## Architecture

This project translates the core architecture of Claude Code (TypeScript/Bun) into Python, preserving the same design patterns:

```
claude-code-python/
├── tool/                    # Tool System (Registry Pattern)
│   ├── base.py              # Tool abstract class + Permission model
│   ├── registry.py          # Global ToolRegistry
│   └── builtin/             # Built-in tool implementations
│       ├── bash.py           # Shell command execution
│       ├── file_read.py      # File reading
│       ├── file_edit.py      # File creation/editing (search & replace)
│       └── glob.py            # File pattern matching
├── agent/                   # Core Agent System
│   ├── context.py           # Message history + token management
│   └── query_engine.py      # Main agent loop (QueryEngine)
├── main.py                 # CLI entry point (typer)
└── requirements.txt
```

## Core Design Patterns

### 1. Tool Pattern (`tool/base.py`)
Every tool implements the `Tool` interface:
- `name`: Unique identifier
- `description`: For LLM to decide when to call
- `input_schema`: JSON Schema for input validation
- `permission`: Permission model (ASK/AUTOMATIC/NEVER)
- `execute(input_data)`: Returns `ToolResult`

### 2. Registry Pattern (`tool/registry.py`)
Global `ToolRegistry` maintains all available tools. Used by:
- QueryEngine to get LLM tool definitions
- Permission system for access control
- CLI for `list-tools` command

### 3. Agent Loop (`agent/query_engine.py`)
```
User Message → Context → LLM API → Response
                                    ↓
              Text Output ←──────┐  Tool Calls
                                 ↓
                          Execute via Registry
                                 ↓
                          Add Results → Context → Loop
```

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Set API key
export ANTHROPIC_API_KEY=sk-ant-...

# Run a task
python main.py "Read ./README.md and explain the project"

# List tools
python main.py list-tools

# Verbose mode
python main.py -v "Create a new Python project"
```

## Key Differences from TypeScript Original

| Aspect | TypeScript (Claude Code) | Python (this repo) |
|--------|--------------------------|-------------------|
| Type validation | Zod | Pydantic |
| CLI framework | Commander.js | Typer |
| LLM SDK | @anthropic-ai/sdk | anthropic Python SDK |
| Terminal output | Bun API/console | Rich |
| Tool execution | Async generators | asyncio subprocess |

## Extending

### Adding a new tool

1. Create `tool/builtin/my_tool.py`:

```python
from tool.base import Tool, ToolResult, Permission, PermissionMode, PermissionScope
from typing import Any, Dict

class MyTool(Tool):
    name = "my_tool"
    description = "Does something useful"
    
    def __init__(self):
        self.permission = Permission(
            mode=PermissionMode.ASK,
            scope=PermissionScope.WRITE,
        )
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "arg": {"type": "string", "description": "An argument"}
            },
            "required": ["arg"]
        }
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        result = do_something(input_data["arg"])
        return ToolResult.ok(result)
```

2. Register in `main.py` → `register_builtin_tools()`

## Status

**Reference Implementation** — This is a pedagogical translation showing the core patterns of Claude Code. It is runnable but not a full-featured replacement.

## License

MIT
