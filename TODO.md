# claude-code-python 待补齐模块规划

> 基于 datalee/claude-code 源码分析
> 参考仓库：https://github.com/datalee/claude-code
> 生成时间：2026-04-01

---

## 一、已实现模块 ✅

| 模块 | 文件数 | 说明 |
|------|--------|------|
| agent/ | 4 | context, query_engine, repl |
| tool/ | 14 | base, registry, 11 builtin tools |
| hook/ | 8 | base, events, registry, 3 builtin |
| memory/ | 4 | base, session, compact |
| state/ | 2 | store |
| coordinator/ | 1 | 多 Agent 协调器 |
| skill/ | 1 | Skill 加载器 |
| mcp/ | 1 | MCP 客户端 |
| main.py | 1 | CLI + REPL + doctor |

**总计：约 36 文件，核心架构已完成**

---

## 二、可补齐模块（按优先级）

### P0 - 核心增强（推荐优先实现）

| 模块 | 来源 | 说明 | 复杂度 |
|------|------|------|--------|
| **memdir/** | datalee | 记忆目录管理 + findRelevantMemories | ⭐⭐ |
| **cost-tracker** | datalee | Token 消耗追踪 + 成本统计 | ⭐⭐ |
| **commands/** | datalee | 完整命令系统（/new, /reset 等） | ⭐⭐ |
| **setup/** | datalee | 首次运行引导配置 | ⭐⭐⭐ |

### P1 - 用户体验增强

| 模块 | 来源 | 说明 | 复杂度 |
|------|------|------|--------|
| **history** | datalee | 命令历史管理 + 搜索 | ⭐⭐ |
| **bootstrap/** | datalee | 启动引导 + 环境检查 | ⭐⭐ |
| **screens/** | datalee | REPL 屏幕 UI（富文本输出） | ⭐⭐⭐ |

### P2 - 高级功能

| 模块 | 来源 | 说明 | 复杂度 |
|------|------|------|--------|
| **voice/** | datalee | 语音交互（TTS/STT） | ⭐⭐⭐ |
| **plugins/** | datalee | 插件系统 | ⭐⭐⭐⭐ |
| **remote/** | datalee | 远程控制 | ⭐⭐⭐ |
| **ink/** | datalee | Ink UI 框架（终端富文本） | ⭐⭐⭐⭐ |

### P3 - 基础设施

| 模块 | 来源 | 说明 | 复杂度 |
|------|------|------|--------|
| **constants/** | datalee | 常量定义 | ⭐ |
| **schemas/** | datalee | JSON Schema 校验 | ⭐⭐ |
| **types/** | datalee | TypeScript 类型定义 | ⭐ |
| **utils/** | datalee | 工具函数库 | ⭐⭐ |

---

## 三、P0 模块详细规划

### 3.1 memdir/ — 记忆目录管理

**源文件：** `datalee/claude-code/src/memdir/`

| 文件 | 功能 |
|------|------|
| `memdir.ts` | 记忆目录管理 |
| `findRelevantMemories.ts` | 语义检索相关记忆 |
| `memoryScan.ts` | 扫描记忆文件 |

**实现目标：**
```python
memdir/
├── __init__.py
├── manager.py      # 记忆目录管理
├── scanner.py       # 文件扫描 + Header 解析
└── relevance.py    # findRelevantMemories 实现
```

**核心设计：**
1. 扫描 `memory/` 目录下所有 `.md` 文件
2. 解析每条记忆的 Header（name, description, tags, mtime）
3. 用 LLM（Sonnet）选择相关记忆
4. 返回命中的记忆文件列表

### 3.2 cost-tracker — Token 消耗追踪

**源文件：** `datalee/claude-code/src/cost-tracker.ts`

**实现目标：**
```python
# 追踪内容
- 输入/输出 token 数
- API 调用次数
- 模型使用分布
- 会话成本统计
- 每日/每周/每月报告
```

### 3.3 commands/ — 完整命令系统

**源文件：** `datalee/claude-code/src/commands/`

**实现目标：**
```python
commands/
├── __init__.py
├── base.py         # 命令基类
├── registry.py     # 命令注册表
└── builtin/
    ├── new.py      # /new 新会话
    ├── reset.py    # /reset 重置
    ├── quit.py     # /quit 退出
    ├── model.py    # /model 切换模型
    ├── cost.py     # /cost 查看成本
    └── history.py  # /history 查看历史
```

### 3.4 setup/ — 首次运行引导

**源文件：** `datalee/claude-code/src/setup.ts`

**实现目标：**
```python
setup/
├── __init__.py
├── wizard.py      # 引导向导
├── check.py       # 环境检查（API key、依赖）
└── config.py      # 配置文件生成
```

---

## 四、TodoList

### Phase 1: 核心增强
- [x] `memdir/` — 记忆目录管理 + findRelevantMemories ✅ 2026-04-01
- [x] `cost-tracker` — Token 消耗追踪 ✅ 2026-04-01
- [x] `commands/` — 完整命令系统 ✅ 2026-04-02
- [x] `setup/` — 首次运行引导 ✅ 2026-04-02

### Phase 2: 用户体验
- [x] `history` — 命令历史管理 ✅ 2026-04-02
- [x] `bootstrap/` — 启动引导 ✅ 2026-04-02
- [ ] `screens/` — REPL 富文本屏幕

### Phase 3: 高级功能
- [ ] `voice/` — 语音交互
- [x] `plugins/` — 插件系统 ✅ 2026-04-02
- [x] `remote/` — 远程控制 ✅ 2026-04-02
- [ ] `ink/` — Ink UI 框架

### Phase 4: 基础设施
- [x] `constants/` — 常量定义 ✅ 2026-04-02
- [x] `schemas/` — JSON Schema 校验 ✅ 2026-04-02
- [x] `utils/` — 工具函数库 ✅ 2026-04-02

---

*最后更新：2026-04-02*
