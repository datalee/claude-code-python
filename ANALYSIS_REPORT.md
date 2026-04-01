# Claude Code Python 实现分析报告

> 项目路径: `claude-code-python/`
> 状态: 🚧 进行中（缺少 memory/hook 模块）
> 对应源码: [instructkr/claude-code](https://github.com/instructkr/claude-code)

---

## 一、整体架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py                              │
│                   (CLI 入口 · typer)                       │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                     QueryEngine                             │
│                   (核心 Agent Loop)                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  while not done:                                     │  │
│  │    response = call_llm(context)                     │  │
│  │    parse tool_calls from response                    │  │
│  │    execute tools via registry                        │  │
│  │    add results to context                            │  │
│  │    repeat                                           │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ AgentContext │  │ ToolRegistry │  │  LLM Client  │
│  (上下文管理) │  │  (工具注册)  │  │  (API 调用)  │
└──────────────┘  └──────────────┘  └──────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Tool (抽象基类)    │
              │  ├─ FileReadTool   │
              │  ├─ FileEditTool   │
              │  ├─ BashTool       │
              │  └─ GlobTool       │
              └─────────────────────┘
```

### 核心模块职责

| 模块 | 文件 | 职责 |
|------|------|------|
| **QueryEngine** | `agent/query_engine.py` | Agent 主循环：发请求→解析→执行→循环 |
| **AgentContext** | `agent/context.py` | 消息历史、token 估算、上下文截断 |
| **ToolRegistry** | `tool/registry.py` | 全局工具注册表，LLM 查询工具 |
| **Tool** | `tool/base.py` | 工具抽象基类 + 权限模型 |
| **内置工具** | `tool/builtin/*.py` | 具体工具实现 |

---

## 二、QueryEngine 详解（核心引擎）

### 2.1 什么是 QueryEngine？

QueryEngine 是 Agent 的**主循环引擎**，对应 Claude Code 源码中的 `src/query.ts`。它驱动整个 Agent 的运转：

```
用户输入 → QueryEngine.run() → LLM API → 解析响应 → 执行工具 → 返回结果
```

### 2.2 核心流程图

```
                    ┌─────────────────┐
                    │  用户输入消息   │
                    └────────┬────────┘
                             ▼
              ┌────────────────────────────┐
              │  self.context.add_user_   │
              │    message(msg)           │
              └────────┬───────────────────┘
                       ▼
         ┌────────────────────────────┐
         │     while 循环开始         │
         │  iteration++              │
         │  state = THINKING         │
         └────────┬───────────────────┘
                  ▼
    ┌─────────────────────────────┐
    │   self._call_llm()         │ ◄─── 核心调用
    │   构造请求:                 │
    │   - model                   │
    │   - max_tokens              │
    │   - messages (上下文)       │
    │   - tools (工具定义)         │
    └────────┬────────────────────┘
             ▼
    ┌─────────────────────────────┐
    │  解析 LLM 响应:            │
    │  - content (文本回复)       │
    │  - tool_calls (工具调用)    │
    └────────┬────────────────────┘
             ▼
    ┌─────────────────────────────────────┐
    │  self.context.add_assistant_message │
    │  (将回复加入上下文)                 │
    └────────┬────────────────────────────┘
             ▼
    ┌─────────────────────────────────────┐
    │  有 tool_calls ?                    │
    └────────┬────────────────────────────┘
             │
     ┌───────┴───────┐
     │ Yes           │ No
     ▼               ▼
    ┌────────┐    ┌─────────────────┐
    │执行工具 │    │  结束 (break)  │
    │循环     │    └─────────────────┘
    └────┬───┘
         ▼
    ┌─────────────────────────────┐
    │  _execute_tool_calls()     │
    │  遍历每个 tool_call:        │
    │  1. lookup tool in registry│
    │  2. check_permission()     │
    │  3. prompt if ASK mode      │
    │  4. tool.execute()         │
    │  5. context.add_tool_result│
    └────────┬────────────────────┘
             ▼
    ┌─────────────────────────────────┐
    │  Check:                         │
    │  - iteration >= max_iterations  │
    │  - _stop_event is set           │
    │  - no more tool_calls           │
    └────────┬────────────────────────┘
             │
      ┌──────┴──────┐
      │ Continue    │──► 回到 while 循环
      │ or Break    │
      └─────────────┘
```

### 2.3 关键类设计

#### AgentConfig（配置类）

```python
@dataclass
class AgentConfig:
    model: str = "claude-sonnet-4-20250514"      # LLM 模型
    max_iterations: int = 100                     # 最大循环次数
    max_tool_calls_per_iteration: int = 128       # 单次最大工具调用数
    temperature: float = 0                        # 温度参数
    system_prompt: Optional[str] = None            # 系统提示词
    stream: bool = True                            # 是否流式输出
    verbose: bool = False                          # 详细模式
```

#### AgentState（状态枚举）

```python
class AgentState(Enum):
    IDLE = "idle"                    # 空闲
    THINKING = "thinking"              # 思考中（调用 LLM）
    TOOL_CALLING = "tool_calling"     # 执行工具中
    AWAITING_PERMISSION = "awaiting_permission"  # 等待用户授权
    DONE = "done"                     # 完成
    ERROR = "error"                   # 错误
```

### 2.4 LLM 调用详解（_call_llm）

```python
async def _call_llm(self) -> Any:
    # 1. 获取或创建 LLM 客户端
    if self.llm_client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.llm_client = AsyncAnthropic(api_key=api_key)
    
    # 2. 构造请求消息
    messages = self.context.get_messages()    # 从上下文获取历史
    tools = self.tool_registry.get_llm_tools() # 获取工具定义
    
    request_options = {
        "model": self.config.model,
        "max_tokens": 8192,
        "messages": messages,
        "tools": tools,
    }
    
    # 3. 发送请求（支持流式）
    if self.config.stream:
        async with self.llm_client.messages.stream(**request_options) as stream:
            response = await stream.get_final_message()
    else:
        response = await self.llm_client.messages.create(**request_options)
    
    return response
```

### 2.5 工具执行详解（_execute_tool_calls）

```python
async def _execute_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> None:
    for tc in tool_calls:
        tool_name = tc["name"]
        tool_input = tc["input"]
        tool_id = tc["id"]
        
        # Step 1: 从注册表查找工具
        tool = self.tool_registry.get(tool_name)
        if tool is None:
            self.context.add_tool_result(f"Unknown tool: {tool_name}", tool_id)
            continue
        
        # Step 2: 权限检查
        allowed, reason = tool.check_permission()
        if not allowed:
            self.context.add_tool_result(f"Permission denied: {reason}", tool_id)
            continue
        
        # Step 3: ASK 模式需用户确认
        if tool.permission.mode == PermissionMode.ASK:
            if not self._prompt_permission(tool):
                self.context.add_tool_result("User denied permission", tool_id)
                continue
        
        # Step 4: 执行工具
        try:
            result = await tool.execute(tool_input)
        except Exception as e:
            result = ToolResult.err(f"Tool execution error: {e}")
        
        # Step 5: 将结果加入上下文
        self.context.add_tool_result(result.content, tool_id)
```

---

## 三、Context 系统详解（上下文管理核心）

Context 系统是 Agent 的**记忆中枢**，负责管理整个对话的生命周期。Agent 做的一切决策都基于上下文，没有上下文就没有智能。

### 3.1 为什么需要 Context 系统？

LLM 有上下文窗口限制（Claude 约 200K tokens）。当对话越来越长时：

```
问题：
1. 对话历史越来越长 → 超过上下文窗口
2. Token 成本越来越高 → 浪费钱
3. 模型容易"遗忘"早期信息 → 决策质量下降

Context 系统解决方案：
1. 跟踪消息历史，自动管理生命周期
2. 精确估算 token，接近上限时截断
3. 优先保留最重要的信息（系统提示 + 最近对话）
```

### 3.2 核心数据结构

#### MessageRole（消息角色枚举）

```python
class MessageRole(Enum):
    """
    消息的发送者角色，决定了 LLM 如何理解这条消息。
    对应 Claude Code 源码: src/context.ts ~Role~
    
    四种角色：
    - system: 系统指令（只读，不计入工具调用）
    - user: 用户输入
    - assistant: LLM 自己的回复
    - tool: 工具执行结果
    """
    SYSTEM = "system"      # 系统提示，最重要，永不删除
    USER = "user"          # 用户消息
    ASSISTANT = "assistant"# LLM 回复（含 tool_calls）
    TOOL = "tool"          # 工具结果
```

#### Message（单条消息）

```python
@dataclass
class Message:
    """
    对应 Claude Code 源码: src/context.ts ~Message~ 接口
    
    一条消息的核心结构：
    - role: 谁说的
    - content: 说了什么
    - tool_calls: 工具调用列表（assistant 消息专用）
    - tool_call_id: 本消息对应的工具调用 ID（tool 消息专用）
    """
    role: MessageRole
    content: str = ""
    tool_calls: Optional[List[Dict[str, Any]]] = None  # assistant 专用
    tool_call_id: Optional[str] = None                  # tool 专用
    name: Optional[str] = None                          # 工具名（tool 专用）
    timestamp: float = field(default_factory=time.time)  # 时间戳
```

**消息生命周期示例：**

```
┌─────────────────────────────────────────────────────────────────┐
│                    一个完整的 Tool Call 对话                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [User]                                                           │
│  { role: "user", content: "Read ./README.md" }                   │
│                                                                  │
│  [Assistant + ToolCall]                                           │
│  {                                                             │
│    role: "assistant",                                           │
│    content: "I'll read the file...",                            │
│    tool_calls: [                                                │
│      { id: "tool_1", name: "read", input: { path: "./README" } }│
│    ]                                                             │
│  }                                                               │
│                                                                  │
│  [Tool Result]                                                    │
│  {                                                             │
│    role: "tool",                                                │
│    content: "# Project\n\nThis is...",                          │
│    tool_call_id: "tool_1",                                      │
│    name: "read"                                                 │
│  }                                                               │
│                                                                  │
│  [Assistant Final]                                                │
│  {                                                             │
│    role: "assistant",                                           │
│    content: "The README contains..."                             │
│  }                                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### ToolCall（工具调用）

```python
@dataclass
class ToolCall:
    """
    代表一次工具调用请求。
    对应 Claude Code 源码: src/context.ts ~ToolCall~ 接口
    
    LLM 生成 tool_calls，格式为：
    {
      "id": "tool_1",           # 唯一标识
      "name": "read",           # 工具名
      "input": { "path": "..." } # 工具参数
    }
    """
    id: str                      # 唯一 ID
    name: str                    # 工具名
    input_data: Dict[str, Any]  # 工具参数
```

#### ToolResultBlock（工具结果块）

```python
@dataclass
class ToolResultBlock:
    """
    工具结果的内容块。
    对应 Claude Code 源码: src/context.ts ~ToolResultBlock~
    
    用于将工具执行结果格式化后返回给 LLM。
    """
    type: str = "tool_result"
    tool_use_id: str = ""       # 对应的 tool_call id
    content: str = ""           # 执行结果内容
```

### 3.3 AgentContext 核心操作

```python
class AgentContext:
    """
    对应 Claude Code 源码: src/context.ts ~Context~ 类
    
    职责：
    1. 存储消息历史（_messages 列表）
    2. 工具结果缓存（_tool_results 字典）
    3. Token 计数与估算
    4. 上下文截断（当超过限制时）
    """
    
    DEFAULT_MAX_TOKENS = 200_000  # Claude 上下文窗口约 200K
    TOKEN_ESTIMATE_CHARS = 4     # 备用估算：1 token ≈ 4 字符
    
    def __init__(self, system_prompt: str = None):
        self._messages: List[Message] = []
        self._tool_results: Dict[str, str] = {}  # tool_id → result
        self.max_tokens = self.DEFAULT_MAX_TOKENS
        self._encoder = None
        
        # 初始化 tiktoken（精确 token 计数）
        try:
            self._encoder = tiktoken.get_encoding("cl100k_base")
        except:
            pass  # 回退到字符估算
```

#### 添加消息

```python
def add_user_message(self, content: str) -> None:
    """添加用户消息"""
    self._messages.append(Message(role=MessageRole.USER, content=content))

def add_assistant_message(self, content: str, tool_calls: List[ToolCall] = None):
    """添加助手消息（可带工具调用）"""
    tc_dicts = [tc.to_dict() for tc in tool_calls] if tool_calls else None
    self._messages.append(Message(
        role=MessageRole.ASSISTANT,
        content=content,
        tool_calls=tc_dicts
    ))

def add_tool_result(self, content: str, tool_call_id: str) -> None:
    """添加工具结果"""
    self._tool_results[tool_call_id] = content
    self._messages.append(Message(
        role=MessageRole.TOOL,
        content=content,
        tool_call_id=tool_call_id
    ))
```

### 3.4 Token 估算系统

```python
def estimate_tokens(self, text: str) -> int:
    """
    精确估算 token 数量。
    
    使用 tiktoken（cl100k_base编码器），这是 Claude 兼容的编码。
    1 token ≈ 4 字符（英文），中文约 1-2 字符/token
    """
    if self._encoder:
        return len(self._encoder.encode(text))
    return len(text) // self.TOKEN_ESTIMATE_CHARS  # 备用估算

def estimate_total_tokens(self) -> int:
    """估算整个上下文的总 token 数"""
    total = 0
    for msg in self._messages:
        total += self.estimate_tokens(msg.content)
    return total
```

**Token 估算示例：**

```
输入: "Hello, world!"
编码: [15339, 11, 1917, 0]
Token 数: 4

输入: "# Title\n这是中文内容"
编码: [35, 5767, 4, 24826, 21487, ...]
Token 数: ~15
```

### 3.5 上下文截断（智能管理）

```python
def truncate_if_needed(self, keep_recent: int = 20) -> List[Message]:
    """
    当上下文超限时，智能截断。
    
    策略：
    1. 保留系统消息（永不动）
    2. 保留最近 N 条消息
    3. 从中间开始删除最旧的消息
    
    对应 Claude Code 源码: src/context.ts ~truncateContext~
    
    为什么这样设计？
    - 系统提示是 Agent 的"个性"，必须保留
    - 最近的消息对当前任务最相关
    - 早期消息可能被"遗忘"影响最小
    """
    removed = []
    
    while self.estimate_total_tokens() > self.max_tokens and len(self._messages) > 2:
        # 跳过系统消息（index 0），从最旧的用户/助手消息开始删
        for i, msg in enumerate(self._messages):
            if msg.role != MessageRole.SYSTEM:
                removed.append(self._messages.pop(i))
                break
    
    return removed  # 返回被删除的消息（可记录日志）
```

**截断示意图：**

```
截断前（假设超限）:
┌──────┬────────────────────────────────────────────────┐
│ Sys  │ [System] You are Claude Code...               │ ◄── 保留
├──────┼────────────────────────────────────────────────┤
│ Msg  │ [User] Read ./README.md                       │
│ Msg  │ [Assistant] I'll read it...                   │
│ Msg  │ [Tool] file content...                        │──► 被删除
│ Msg  │ [Assistant] The file shows...                 │──► 被删除
│ Msg  │ [User] Now edit main.py                       │──► 被删除
│ Msg  │ [Assistant] I'll edit...                      │ ◄── 保留
│ Msg  │ [Tool] edit complete                          │ ◄── 保留
└──────┴────────────────────────────────────────────────┘

截断后:
┌──────┬────────────────────────────────────────────────┐
│ Sys  │ [System] You are Claude Code...               │
├──────┼────────────────────────────────────────────────┤
│ Msg  │ [Assistant] I'll edit...                      │
│ Msg  │ [Tool] edit complete                          │
└──────┴────────────────────────────────────────────────┘
```

### 3.6 消息格式化（API 对接）

```python
def get_messages(self) -> List[Dict[str, Any]]:
    """
    将消息格式化为 LLM API 格式。
    
    对应 Claude Code 源码: src/context.ts ~formatMessages~
    
    返回格式符合 Anthropic API 要求：
    [
        { "role": "system", "content": "..." },
        { "role": "user", "content": "..." },
        { "role": "assistant", "content": "...", "tool_calls": [...] },
        { "role": "tool", "content": "...", "tool_call_id": "..." }
    ]
    """
    return [msg.to_dict() for msg in self._messages]
```

### 3.7 上下文系统与 QueryEngine 的协作

```
┌─────────────────────────────────────────────────────────────────┐
│                        QueryEngine.run()                        │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. 用户输入                                                     │
│     engine.context.add_user_message("Read ./README.md")         │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. 首次 LLM 调用                                                │
│     messages = context.get_messages()  # 获取格式化消息           │
│     response = await call_llm(messages, tools)                   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. LLM 返回 tool_call                                           │
│     context.add_assistant_message(response.content, tool_calls)   │
│                                                                  │
│     # 此时上下文已包含:                                           │
│     # - System                                                    │
│     # - User: Read ./README.md                                   │
│     # - Assistant: I'll read it... + tool_calls                 │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. 执行工具                                                      │
│     result = await tool.execute(input)                          │
│     context.add_tool_result(result, tool_call_id)               │
│                                                                  │
│     # 上下文新增:                                                 │
│     # - Tool: file content (tool_call_id: tool_1)               │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. 再次 LLM 调用（带上工具结果）                                  │
│     # LLM 看到工具结果后，给出最终回复                            │
│     context.add_assistant_message("The file contains...")       │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  6. Token 检查                                                    │
│     if context.estimate_total_tokens() > context.max_tokens:     │
│         context.truncate_if_needed()  # 智能截断                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.8 与 Claude Code 源码的精确对应

| 本项目 | Claude Code 源码 | 说明 |
|--------|-----------------|------|
| `MessageRole` | `src/context.ts ~Role~` | 消息角色枚举 |
| `Message` | `src/context.ts ~Message~` | 单条消息 |
| `AgentContext` | `src/context.ts ~Context~` | 上下文管理器 |
| `ToolCall` | `src/context.ts ~ToolCall~` | 工具调用对象 |
| `ToolResultBlock` | `src/context.ts ~ToolResultBlock~` | 工具结果块 |
| `get_messages()` | `src/context.ts ~formatMessages~` | 格式化 API 消息 |
| `truncate_if_needed()` | `src/context.ts ~truncateContext~` | 上下文截断 |

---

## 四、Tool 系统详解

### 4.1 Tool 抽象基类

```python
class Tool(ABC):
    """所有工具的基类，定义统一接口"""
    
    name: str = ""              # 工具唯一标识
    description: str = ""       # 供 LLM 理解的描述
    permission: Permission = Permission()  # 权限配置
    
    @abstractmethod
    def get_input_schema(self) -> Dict[str, Any]:
        """返回 JSON Schema，LLM 据此构造调用参数"""
        raise NotImplementedError
    
    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """核心执行逻辑"""
        raise NotImplementedError
```

### 4.2 权限模型（三级权限）

```python
class PermissionMode(Enum):
    ASK = "ask"           # 每次执行前询问用户
    AUTOMATIC = "automatic" # 自动执行（可信操作）
    NEVER = "never"       # 禁用

class PermissionScope(Enum):
    READ = "read"         # 只读操作
    WRITE = "write"       # 写操作
    NETWORK = "network"   # 网络访问
    ENVIRONMENT = "environment"  # 环境变量
    ALL = "all"           # 全部权限
```

### 4.3 内置工具一览

| 工具 | 文件 | 核心功能 |
|------|------|----------|
| **BashTool** | `tool/builtin/bash.py` | 执行 shell 命令 |
| **FileReadTool** | `tool/builtin/file_read.py` | 读取文件内容 |
| **FileEditTool** | `tool/builtin/file_edit.py` | Search-replace 编辑 |
| **GlobTool** | `tool/builtin/glob.py` | 模式匹配文件 |

### 4.4 FileEditTool 详解（Search-Replace 模式）

```python
class FileEditTool(Tool):
    """
    通过 'old_text' 精确匹配实现文件编辑
    LLM 必须提供 exact old_text 来定位编辑位置
    """
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        file_path = input_data["file_path"]
        old_text = input_data["old_text"]
        new_text = input_data.get("new_text", "")
        
        # 1. 读取原文件
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 2. 验证 old_text 精确匹配
        if old_text not in content:
            return ToolResult.err(f"old_text not found in file")
        
        # 3. 执行替换
        new_content = content.replace(old_text, new_text, 1)
        
        # 4. 写回文件
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        
        return ToolResult.ok(f"Edited {file_path}")
```

---

## 五、ToolRegistry 注册表模式

### 5.1 核心设计

```python
class ToolRegistry:
    """全局工具注册表（单例模式）"""
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """注册工具"""
        self._tools[tool.name] = tool
    
    def get(self, name: str) -> Optional[Tool]:
        """根据名称获取工具"""
        return self._tools.get(name)
    
    def get_llm_tools(self) -> List[Dict[str, Any]]:
        """获取所有工具的 LLM 定义"""
        return [tool.get_metadata() for tool in self._tools.values()]
```

### 5.2 注册流程

```python
# main.py 启动时
registry = ToolRegistry()

# 注册内置工具
registry.register(FileReadTool())
registry.register(FileEditTool())
registry.register(BashTool())
registry.register(GlobTool())

# 将注册表注入 QueryEngine
engine = QueryEngine(tool_registry=registry)
```

---

## 六、与 Claude Code 源码的对应关系

| 本项目 | Claude Code 源码 | 说明 |
|--------|------------------|------|
| `agent/query_engine.py` | `src/query.ts` | 核心 QueryEngine 类 |
| `agent/context.py` | `src/context.ts` | Context 类 + Message |
| `tool/base.py` | `src/Tool.ts` | Tool 抽象类 + PermissionModel |
| `tool/registry.py` | `src/tools.ts` | 工具注册表 |
| `tool/builtin/*.py` | `src/tools/*.ts` | 内置工具实现 |

### Claude Code 完整模块树（~1900 文件）

```
src/
├── main.tsx              # CLI 入口
├── query.ts              # QueryEngine 核心
├── context.ts            # 上下文管理
├── Tool.ts               # Tool 基类
├── tools.ts              # 工具注册表
├── tools/                # 内置工具 (~40 个)
│   ├── BashTool.ts
│   ├── FileReadTool.ts
│   ├── FileEditTool.ts
│   ├── GlobTool.ts
│   ├── GrepTool.ts
│   ├── WebSearchTool.ts
│   ├── AgentTool.ts      # 子 Agent
│   ├── TaskTool.ts       # 任务管理
│   └── ...
├── state/                # Zustand 状态管理
├── coordinator/          # 多 Agent 协作
├── skill/                # Skill 系统
├── mcp/                  # MCP 协议
└── hooks/                # 钩子系统
```

---

## 七、设计模式总结

| 模式 | 应用场景 |
|------|----------|
| **Template Method** | Tool 基类定义骨架，子类实现 `execute()` |
| **Strategy** | 不同工具封装不同策略 |
| **Registry/Singleton** | 全局 ToolRegistry |
| **Command** | 每个 Tool 是一个可执行的命令对象 |
| **Observer** | 进度条监听工具执行状态 |
| **Factory** | Tool 子类实例化 |

---

## 八、待完成模块

### 8.1 Memory 模块（记忆系统）

| 文件 | 功能 |
|------|------|
| `memory/base.py` | 记忆抽象基类 |
| `memory/session.py` | 会话记忆管理 |
| `memory/compact.py` | 上下文压缩 |

### 8.2 Hook 模块（钩子系统）

| 文件 | 功能 |
|------|------|
| `hook/base.py` | 钩子抽象基类 |
| `hook/registry.py` | 钩子注册表 |
| `hook/events.py` | 事件类型定义 |
| `hook/builtin/session_memory.py` | 会话记忆钩子 |
| `hook/builtin/command_logger.py` | 命令日志钩子 |
| `hook/builtin/boot_md.py` | 启动钩子 |

---

## 九、运行方式

```bash
cd claaude-code-python

pip install -r requirements.txt
set ANTHROPIC_API_KEY=sk-ant-...   # Windows
# export ANTHROPIC_API_KEY=sk-ant-...  # Linux/Mac

# 运行
python main.py "Read ./README.md and explain"
python main.py list-tools
```

---

*报告生成时间: 2026-04-01*
*最后更新: 2026-04-01 05:22*
