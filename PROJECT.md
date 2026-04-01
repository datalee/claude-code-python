# Claude Code 源码分析翻译项目

## 项目概述

| 属性 | 内容 |
|------|------|
| 目标 | 将 Claude Code TypeScript 源码翻译为 Python 实现 |
| 来源 | [instructkr/claude-code](https://github.com/instructkr/claude-code) (npm source map 泄露) |
| 规模 | ~1,900 文件，512,000+ 行 TypeScript |
| 状态 | 🚧 进行中 |
| 文档 | `ANALYSIS_REPORT.md` - 完整分析报告 |

---

## 已完成模块 ✅

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| QueryEngine | `agent/query_engine.py` | ✅ | Agent Loop 核心引擎 |
| AgentContext | `agent/context.py` | ✅ | 消息历史 + Token 估算 |
| Tool 基类 | `tool/base.py` | ✅ | 抽象基类 + 权限模型 |
| ToolRegistry | `tool/registry.py` | ✅ | 全局工具注册表 |
| BashTool | `tool/builtin/bash.py` | ✅ | Shell 命令执行 |
| FileReadTool | `tool/builtin/file_read.py` | ✅ | 文件读取 |
| FileEditTool | `tool/builtin/file_edit.py` | ✅ | Search-replace 编辑 |
| GlobTool | `tool/builtin/glob.py` | ✅ | 模式匹配文件 |

---

## Todo List 📋

### P0 - 核心系统（必须完成）

#### ✅ memory 模块（记忆系统）- 2026-04-01 完成
> 负责会话上下文持久化，自动压缩前刷新

| 文件 | 状态 | 说明 |
|------|------|------|
| `memory/__init__.py` | ✅ | 模块初始化 + 导出 |
| `memory/base.py` | ✅ | MemoryBase 抽象基类 + MemoryEntry |
| `memory/session.py` | ✅ | SessionMemory 会话管理器 |
| `memory/compact.py` | ✅ | CompactionManager 压缩管理器 |

**功能点：**
- ✅ 记忆写入/读取接口（MemoryBase 抽象）
- ✅ 会话生命周期管理（SessionMemory）
- ✅ Token 估算与压缩策略（CompactionManager）
- ✅ 记忆层级管理（日记/长期/会话）
- [ ] `memory/vector.py` - 向量记忆搜索（可选）

**对应 Claude Code 源码:** `src/memory/*.ts`

#### ✅ hook 模块（钩子系统）- 2026-04-01 完成
> 事件驱动的自动化，执行 /new、/reset 等命令时触发

| 文件 | 状态 | 说明 |
|------|------|------|
| `hook/__init__.py` | ✅ | 模块初始化 + 导出 |
| `hook/events.py` | ✅ | EventType + HookEvent + EventFilter |
| `hook/base.py` | ✅ | Hook 抽象基类 + HookConfig + HookResult |
| `hook/registry.py` | ✅ | HookRegistry 注册表 + 全局单例 |
| `hook/builtin/__init__.py` | ✅ | 内置钩子导出 |
| `hook/builtin/session_memory.py` | ✅ | SessionMemoryHook 会话记忆钩子 |
| `hook/builtin/command_logger.py` | ✅ | CommandLoggerHook 命令日志钩子 |
| `hook/builtin/boot_md.py` | ✅ | BootMdHook 启动钩子 |

**功能点：**
- ✅ 钩子注册与发现机制（HookRegistry）
- ✅ 事件类型：gateway:startup, command:new, session:end 等
- ✅ 内置钩子：session-memory、command-logger、boot-md
- ✅ 事件过滤器（EventFilter）
- ✅ 异步执行 + 重试机制

**对应 Claude Code 源码:** `src/hooks/*.ts`

---

### P1 - 核心交互

#### ✅ agent/repl.py（REPL 交互界面）- 2026-04-01 完成
> 交互式命令行界面，用户输入 → QueryEngine → 输出

| 功能 | 状态 | 说明 |
|------|------|------|
| REPL 主循环 | ✅ | async run() 异步循环 |
| 命令行提示符 | ✅ | prompt / multiline_prompt |
| 多行输入支持 | ✅ | 检测 \\ 或 : 或缩进 |
| Ctrl+C / Ctrl+D | ✅ | 中断和退出处理 |
| 历史命令记录 | ✅ | readline + 历史文件 |
| 内置命令 | ✅ | /quit, /new, /reset, /help 等 |
| Hook 事件 | ✅ | session:start/end, command:new |

**对应 Claude Code 源码:** `src/repl/*.ts`

#### ✅ main.py（CLI 重构）- 2026-04-01 完成
> 命令行入口，整合所有模块

| 功能 | 状态 | 说明 |
|------|------|------|
| 命令解析 | ✅ | typer + 子命令 |
| 子命令 | ✅ | main, repl, list-tools, list-hooks, doctor |
| 配置加载 | ✅ | Config.from_env() 环境变量 |
| 工具注册 | ✅ | register_builtin_tools() |
| 钩子注册 | ✅ | register_builtin_hooks() |
| REPL 集成 | ✅ | _run_repl() 异步 REPL |
| Doctor 诊断 | ✅ | doctor 命令健康检查 |

**对应 Claude Code 源码:** `src/main.tsx`

#### ✅ state/store.py（状态管理）- 2026-04-01 完成
> 全局状态管理，类似 Zustand

| 组件 | 状态 | 说明 |
|------|------|------|
| Store | ✅ | 状态容器（get/set/subscribe） |
| Selector | ✅ | 状态选择器（派生状态） |
| Subscription | ✅ | 订阅管理（Subscription） |
| Middleware | ✅ | 中间件基类 |
| LoggerMiddleware | ✅ | 日志中间件 |
| PersistMiddleware | ✅ | 持久化中间件 |

**对应 Claude Code 源码:** `src/state/*.ts`

---

### P2 - 内置工具扩展

#### ✅ 搜索类工具 - 2026-04-01 完成

| 工具 | 文件 | 功能 |
|------|------|------|
| ✅ GrepTool | `tool/builtin/grep.py` | 代码内容搜索（正则/上下文） |
| ✅ WebSearchTool | `tool/builtin/web_search.py` | 网络搜索（多后端） |
| ✅ WebFetchTool | `tool/builtin/web_fetch.py` | 网页内容抓取（HTML解析） |

#### ✅ Agent 类工具 - 2026-04-01 完成

| 工具 | 文件 | 功能 |
|------|------|------|
| ✅ AgentTool | `tool/builtin/agent.py` | 启动子 Agent |
| ✅ TeamCreateTool | `tool/builtin/agent.py` | 创建 Agent 团队 |

#### ✅ 任务管理工具 - 2026-04-01 完成

| 工具 | 文件 | 功能 |
|------|------|------|
| ✅ TaskCreateTool | `tool/builtin/task.py` | 创建任务 |
| ✅ TaskListTool | `tool/builtin/task.py` | 任务列表 |
| ✅ TaskUpdateTool | `tool/builtin/task.py` | 更新任务 |

#### ✅ Git 工具 - 2026-04-01 完成

| 工具 | 文件 | 功能 |
|------|------|------|
| ✅ EnterWorktreeTool | `tool/builtin/worktree.py` | 进入/创建 Git Worktree |
| ✅ ExitWorktreeTool | `tool/builtin/worktree.py` | 退出/删除 Git Worktree |
| ✅ ListWorktreesTool | `tool/builtin/worktree.py` | 列出所有 Worktree |

#### ✅ 其他杂项工具 - 2026-04-01 完成

| 工具 | 文件 | 功能 |
|------|------|------|
| ✅ SleepTool | `misc.py` | 延时等待 |
| ✅ EnterPlanModeTool | `misc.py` | 进入计划模式 |
| ✅ ExitPlanModeTool | `misc.py` | 退出计划模式 |
| ✅ ScheduleCronTool | `misc.py` | 定时任务 |
| ✅ ReadClipboardTool | `misc.py` | 读剪贴板 |
| ✅ WriteClipboardTool | `misc.py` | 写剪贴板 |

#### ✅ LSP 工具 - 2026-04-01 完成

| 工具 | 文件 | 功能 |
|------|------|------|
| ✅ LSPTool | `lsp.py` | 代码跳转/引用/悬停/补全 |

**内置工具总计：18 个 ✅**

**P2 内置工具全部完成**

---

### P3 - 高级功能 ✅

#### ✅ coordinator/（多 Agent 协作）- 2026-04-01 完成

| 组件 | 状态 | 说明 |
|------|------|------|
| Coordinator | ✅ | 多 Agent 协调器 |
| CoordinatorTask | ✅ | 任务定义 |
| AgentInfo | ✅ | Agent 信息 |
| 任务分发 | ✅ | 自动分配给空闲 Agent |
| 结果汇总 | ✅ | 收集所有结果 |

**对应 Claude Code 源码:** `src/coordinator/*.ts`

#### ✅ skill/（Skill 系统）- 2026-04-01 完成

| 组件 | 状态 | 说明 |
|------|------|------|
| Skill 基类 | ✅ | Skill 抽象基类 |
| SkillLoader | ✅ | Skill 加载器 |
| SkillRunner | ✅ | Skill 执行器 |
| SkillContext | ✅ | 执行上下文 |
| 内置 Skill | ✅ | HelloWorld/FileWriter/Shell |

**对应 Claude Code 源码:** `src/skill/*.ts`

---

### P4 - 协议集成 ✅

#### ✅ mcp/（MCP 协议）- 2026-04-01 完成

| 组件 | 状态 | 说明 |
|------|------|------|
| MCPClient | ✅ | MCP 客户端（stdio 连接） |
| MCPToolAdapter | ✅ | MCP 工具适配器 |
| MCPManager | ✅ | MCP 服务器管理器 |
| 工具调用 | ✅ | call_tool 接口 |
| 资源读取 | ✅ | read_resource 接口 |

**对应 Claude Code 源码:** `src/mcp/*.ts`
**参考:** https://modelcontextprotocol.io/

---

## 项目结构

```
claude-code-python/
├── main.py                      # ✅ CLI 入口（已重构）
├── requirements.txt
├── agent/
│   ├── __init__.py
│   ├── query_engine.py          # ✅ 已完成
│   ├── context.py               # ✅ 已完成
│   └── repl.py                  # ✅ 已完成
├── tool/
│   ├── __init__.py
│   ├── base.py                 # ✅ 已完成
│   ├── registry.py             # ✅ 已完成
│   └── builtin/
│       ├── bash.py             # ✅ 已完成
│       ├── file_read.py        # ✅ 已完成
│       ├── file_edit.py        # ✅ 已完成
│       ├── glob.py             # ✅ 已完成
│       ├── grep.py             # 🔲 待开发
│       ├── web_search.py       # 🔲 待开发
│       ├── web_fetch.py        # 🔲 待开发
│       ├── agent.py            # 🔲 待开发
│       ├── team.py             # 🔲 待开发
│       ├── task_*.py           # 🔲 待开发
│       ├── worktree_*.py      # 🔲 待开发
│       ├── mcp.py              # 🔲 待开发
│       └── ...
├── memory/                      # ✅ P0 已完成
│   ├── __init__.py
│   ├── base.py
│   ├── session.py
│   └── compact.py
├── hook/                        # ✅ P0 已完成
│   ├── __init__.py
│   ├── base.py
│   ├── registry.py
│   ├── events.py
│   └── builtin/
│       ├── __init__.py
│       ├── session_memory.py
│       ├── command_logger.py
│       └── boot_md.py
├── state/                       # ✅ P1 已完成
│   ├── __init__.py
│   └── store.py
├── coordinator/                 # 🔲 P3 待开发
│   └── __init__.py
├── skill/                       # ✅ P3 已完成
│   └── __init__.py
└── mcp/                         # ✅ P4 已完成
    └── __init__.py
```

---

## 进度追踪

---

## 进度追踪

| 日期 | 完成内容 | 备注 |
|------|----------|------|
| 2026-03-31 | agent/query_engine, agent/context, tool/* | 基础架构完成 |
| 2026-04-01 | 创建 PROJECT.md + ANALYSIS_REPORT.md | 项目规划 + 分析报告 |
| 2026-04-01 | ✅ memory/ | 记忆模块 |
| 2026-04-01 | ✅ hook/ | 钩子模块 |
| 2026-04-01 | ✅ agent/repl.py + main.py | REPL + CLI |
| 2026-04-01 | ✅ state/store.py | 状态管理 |
| 2026-04-01 | ✅ 内置工具 18 个（含 LSPTool） | P2 全部完成 |
| 2026-04-01 | ✅ coordinator/ + skill/ | P3 全部完成 |
| 2026-04-01 | ✅ mcp/ | P4 全部完成 |

---

## 黄金守则

> ⚠️ **每次完成一个模块，必须立即更新此文档！**
> - 完成某个文件 → 在上方表格打 ✅
> - 完成某个功能点 → 在 checkbox 框打 ✅
> - 每次更新后更新时间戳

---

*最后更新: 2026-04-01 05:26*
