# TODO.md - claude-code-python 项目追踪

> 最后更新：2026-04-02

---

## 一、代码中的 TODO（必须完成）

### 🔴 高优先级（影响核心功能）

| 文件 | 行 | 内容 | 状态 |
|------|-----|------|------|
| `agent/query_engine.py` | 496 | ✅ 交互式权限确认（typer prompt）| ✅ 已完成 |
| `agent/query_engine.py` | 534 | TODO: Add support for resumable sessions (save/load context) | 🟡 待处理 |
| `agent/query_engine.py` | 535 | ✅ Agent 循环已支持多轮连续工具调用 | ✅ 已完成 |
| `agent/query_engine.py` | 536 | ✅ 错误恢复和重试逻辑（指数退避） | ✅ 已完成 |

### 🟡 中优先级（影响用户体验）

| 文件 | 行 | 内容 | 状态 |
|------|-----|------|------|
| `hook/base.py` | 303 | ✅ Hook 超时控制（asyncio.wait_for） | ✅ 已完成 |
| `memory/compact.py` | 233 | ✅ 删除策略：LONG_TERM/高优/新记忆不删除 | ✅ 已完成 |
| `memory/session.py` | 328 | ✅ 关键词精确匹配：TF-IDF + 优先级 + 时间衰减 | ✅ 已完成 |
| `memory/session.py` | 396 | ✅ 追加到 memory/long-term.md | ✅ 已完成 |
| `memory/session.py` | 401 | ✅ 单条决策追加到 long-term.md | ✅ 已完成 |

### 🟢 低优先级（nice to have）

| 文件 | 行 | 内容 | 状态 |
|------|-----|------|------|
| `plugins/__init__.py` | 394 | ✅ install_plugin 本地/pip 安装 | ✅ 已完成 |
| `plugins/__init__.py` | 407 | ✅ uninstall_plugin 卸载 | ✅ 已完成 |
| `tool/builtin/file_edit.py` | 270 | ✅ multi-replace 批量替换 | ✅ 已完成 |
| `tool/builtin/file_edit.py` | 271 | ✅ undo/rollback 撤销功能 | ✅ 已完成 |

---

## 二、项目完成度

### 核心功能
| 模块 | 状态 | 说明 |
|------|-------|------|
| REPL | ✅ 完成 | 可正常对话 |
| SkillTool | ✅ 完成 | function call 集成 |
| Tools 注册 | ✅ 完成 | 18 个工具已注册 |
| Tool 调用 | ✅ 完成 | bash, glob, read 等 |
| API 调用 | ✅ 完成 | anthropic SDK + OpenAI 兼容 |

### 缺失的重要功能
| 功能 | 状态 | 说明 |
|------|-------|------|
| SkillTool skill 内容注入 | ✅ 已修复 | 改为 system role 注入上下文 |
| Interactive permission prompt | ✅ 已完成 | typer Confirm.ask + --non-interactive |
| Session save/resume | ✅ 已完成 | AgentContext.save()/load() 方法 |

---

## 三、修复记录

### 2026-04-02

| 问题 | 修复 | 状态 |
|------|------|------|
| 重复 `_call_llm` 函数 | 删除旧版本，保留 OpenAI 兼容版 | ✅ |
| `SkillTool` 继承 Tool 基类 | 添加 `super().__init__()` | ✅ |
| `SkillTool` 返回 new_messages | 通过 metadata 传递 | ✅ |
| Tool call tool role 转换 | Volcengine 不支持 tool role | ✅ |

---

## 四、下一步计划

### 1. 立即修复 🔴
- [ ] **Interactive permission prompt** — 用 typer 实现交互式权限确认
- [ ] **Session save/resume** — 支持会话持久化

### 2. 近期完成 🟡
- [ ] **Memory session** — 关键词匹配、记忆追加
- [ ] **Error recovery** — 添加重试逻辑

### 3. 后续优化 🟢
- [ ] **File edit undo** — 文件编辑回滚
- [ ] **Multi-replace** — 批量替换

---

## 五、已解决的用户体验问题

### REPL 改进 ✅
- 命令补全（Tab 键）— prompt_toolkit 实现
- 交互模式自动启用，管道/非交互模式回退
- 输出美化（Rich Markdown 渲染）
- 彩色提示符

---

## 六、已验证可运行

```bash
# REPL 模式
python main.py repl

# 列出工具
python main.py list-tools

# 系统检查
python main.py doctor

# 调用 skill
>>> Use the web-access skill
```

---

*按优先级处理，遇到 blocking 问题及时汇报*
