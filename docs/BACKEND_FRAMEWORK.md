# 后端框架

> KNOT 后端模块结构、职责边界与接口契约。所有代码依此框架编写，不越界。

## 一、包结构

```
knot/                       # 根包
├── core/                   # 共享基础设施（不依赖其他子包）
├── llm/                    # LLM Provider 抽象层（只依赖 core）
├── knowledge_layer/        # 知识增强层（依赖 core + llm）
├── orchestration_layer/    # 任务编排层（依赖 core + llm + knowledge_layer）
├── execution_layer/        # 执行适配层（依赖 core）
├── api/                    # API 层（依赖以上所有，只做路由编排，不含业务逻辑）
└── cli/                    # CLI 入口（依赖 api 初始化逻辑）
```

依赖方向：`core ← llm ← knowledge ← orchestration ← api`

## 二、模块职责

### core/ — 核心基础设施
```
core/
├── models.py       实体模型：Workflow, Node, Edge, Agent, Execution, ToolDefinition
├── config.py       应用配置（pydantic-settings，从 env 加载）
└── exceptions.py   自定义异常层次
```
- 不依赖任何其他 knot 子包
- 纯数据定义，不含业务逻辑

### llm/ — LLM Provider 抽象层
```
llm/
├── base.py         LLMProvider 抽象接口：chat(), embed()
├── deepseek.py     DeepSeek 实现（OpenAI 兼容 SDK）
└── registry.py     ProviderRegistry：注册、获取、init_default_providers()
```
- 职责：封装 LLM 调用差异，向上层提供统一接口
- 追加新供应商：在 llm/ 下新建 provider，实现 LLMProvider 接口，在 registry 中注册

### knowledge_layer/ — 知识增强层
```
knowledge_layer/
├── vector_store.py  Milvus 连接、集合管理、向量检索
├── retriever.py     混合检索器（向量检索 + 关键词）
└── enhancer.py      上下文增强（将检索结果注入提示词模板）
```
- 职责：接收查询 → 检索知识 → 返回增强后的上下文
- 对外接口：HybridRetriever.retrieve(collection, query) → list[KnowledgeChunk]

### orchestration_layer/ — 任务编排层（核心）
```
orchestration_layer/
├── intent.py     意图理解：LLM 将自然语言转为结构化意图
├── planner.py    任务规划：意图 → DAG 工作流
├── workflow.py   工作流引擎：LangGraph 执行 DAG
├── scheduler.py  智能体调度：任务 → Agent
└── state.py      状态管理：全局上下文读写
```
- 执行链路：intent → planner → workflow(scheduler)
- workflow.py 是唯一实际调用 LangGraph 的地方

### execution_layer/ — 执行适配层
```
execution_layer/
├── base.py       BaseTool 抽象接口
├── registry.py   ToolRegistry 注册中心
└── tool_executor.py  内置工具（Echo, HTTP, Calculator）
```
- 追加新工具：实现 BaseTool → registry.register()
- 工具调用在 workflow.py 的 node 执行逻辑中触发

### api/ — API 层
```
api/
├── app.py         FastAPI 应用工厂（初始化所有组件）
└── routes/
    ├── workflows.py  工作流 CRUD + 执行
    ├── knowledge.py  知识库管理 + 搜索
    └── agents.py     智能体注册与管理
```
- 职责：路由注册、请求/响应序列化
- 不含业务逻辑，全部委托给下层

### cli/ — CLI
```
cli/
└── main.py        argparse 入口：knot run / knot serve / knot workflow
```

## 三、层间接口契约

| 接口方向 | 调用方 → 被调用方 | 方法签名 |
|----------|-------------------|----------|
| 编排层→LLM | workflow → provider | `provider.chat(messages, model, temp)` → `LLMResponse` |
| 编排层→知识 | workflow → retriever | `retriever.retrieve(collection, query)` → `list[KnowledgeChunk]` |
| 编排层→知识 | workflow → enhancer | `enhancer.enhance(query, chunks)` → `str` |
| 编排层→调度 | workflow → scheduler | `scheduler.assign_node(node, context)` → `Agent` |
| 编排层→工具 | workflow → registry | `tool_registry.execute(name, params)` → `ToolResult` |
| API→编排层 | routes → engine | `engine.execute(workflow)` → `Execution` |

## 四、代码规范

1. **包间引用**：只能从上向下依赖，禁止反向依赖
2. **模型定义**：只集中在 core/models.py，各层引用不重复定义
3. **异步优先**：所有 I/O 操作使用 async/await
4. **错误处理**：使用 core/exceptions.py 中的自定义异常
5. **配置**：所有环境变量通过 core/config.py 的 Settings 访问
