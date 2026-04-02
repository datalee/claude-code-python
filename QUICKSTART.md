# Quick Start - Claude Code Python CLI

## 1. 安装

```bash
git clone https://github.com/datalee/claude-code-python.git
cd claude-code-python
pip install -r requirements.txt
```

## 2. 配置 API Key

创建 `.env` 文件：

```bash
cp .env.example .env
```

编辑 `.env`：

```env
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
```

或者设置环境变量：

```bash
# Linux/macOS
export ANTHROPIC_API_KEY=sk-ant-your-api-key-here

# Windows PowerShell
$env:ANTHROPIC_API_KEY="sk-ant-your-api-key-here"
```

## 3. 运行

### 单次任务模式（默认）

```bash
python main.py "解释这个项目的结构"
python main.py "创建一个 hello.py 文件"
python main.py "运行 git status"
```

### 交互式 REPL 模式

```bash
python main.py repl
```

进入交互式界面：

```
┌─────────────────────────────────────────────────┐
│  Claude Code Python - REPL Mode                 │
│  Type your request or /help for commands        │
└─────────────────────────────────────────────────┘

> 你好
[Claude] 你好！有什么我可以帮你的吗？

> 帮我写一个快速排序
[Claude] 我来帮你实现快速排序算法...
[TOOL CALL] write_file(hello.py)
[TOOL RESULT] File created: hello.py

> /help
Available commands:
  /help     - Show this help
  /exit     - Exit REPL
  /clear    - Clear conversation
  /tools    - List available tools
  /model    - Show current model
```

### 检查系统状态

```bash
python main.py doctor
```

输出：

```
┌─────────────────────────────────────────────────┐
│ Claude Code Python - Doctor                      │
└─────────────────────────────────────────────────┘
✓ Python 3.12
✓ anthropic SDK installed
✓ tiktoken installed
✓ 18 tools registered
✓ 3 hooks registered
✓ API key configured
```

### 列出所有工具

```bash
python main.py list-tools
```

### Verbose 模式（显示详细日志）

```bash
python main.py -v "创建项目"
```

## 4. REPL 内置命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助 |
| `/exit` | 退出 REPL |
| `/clear` | 清空对话上下文 |
| `/tools` | 列出可用工具 |
| `/model` | 显示当前模型 |
| `/status` | 显示状态信息 |

## 5. 示例对话

```
$ python main.py repl

> 读取当前目录有哪些文件
[Claude] 我来查看一下当前目录的文件...

[TOOL CALL] glob(pattern="*")
[TOOL RESULT] Found 5 files:
  main.py
  README.md
  requirements.txt
  ...

> 帮我创建一个简单的计算器

[Claude] 好的，我来创建一个计算器程序...

[TOOL CALL] write_file(path="calculator.py", content="...")
[TOOL RESULT] File created: calculator.py

> 运行测试一下

[TOOL CALL] bash(command="python calculator.py")
[TOOL RESULT] 1 + 2 = 3
            10 - 5 = 5
            3 * 4 = 12
```

## 6. 常见问题

**Q: 提示 `ANTHROPIC_API_KEY not set`**
A: 确保已设置环境变量或创建了 `.env` 文件

**Q: Windows 上中文显示乱码**
A: 设置环境变量后运行：
```powershell
$env:PYTHONIOENCODING='utf-8'
python main.py repl
```

**Q: 如何切换模型？**
A: 设置 `CLAUDE_CODE_MODEL` 环境变量或在 `.env` 中配置

## 7. 下一步

- 查看 `python main.py list-tools` 了解所有可用工具
- 查看 `python main.py doctor` 检查系统状态
- 阅读 `README.md` 了解项目架构
