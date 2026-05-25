# 前端框架

> KNOT 前端页面结构、组件树与数据流。所有代码依此框架编写，不越界。

## 一、页面规划

```
路由             页面         核心功能
/                → 重定向
/workflows      WorkflowList    展示工作流列表、新建入口
/workflows/:id  WorkflowEditor  React Flow 画布编辑、执行、查看结果
/knowledge      KnowledgeBase   知识库管理与检索测试（Phase 2）
/settings       Settings        系统配置（Phase 2）
```

MVP 覆盖前两个页面。

## 二、组件树

```
App
├── AppHeader                   导航栏（菜单路由）
├── WorkflowList                工作流列表
│   ├── Card × N               每个工作流卡片
│   └── Empty                  空状态
└── WorkflowEditor             工作流编辑器
    ├── Toolbar                顶部工具栏（返回/保存/执行）
    ├── ReactFlow              画布
    │   ├── Background         网格背景
    │   ├── Controls           缩放控制
    │   └── MiniMap            缩略图
    ├── NodePalette            [待建] 组件面板（拖拽来源）
    ├── NodeDetailDrawer       [待建] 节点属性编辑
    └── ExecutionDrawer        执行结果抽屉
```

## 三、状态管理 (Zustand)

```
workflowStore
├── workflows: Workflow[]           列表页数据
├── currentWorkflow: Workflow|null  当前编辑的工作流
├── loading: boolean
├── setWorkflows()
├── setCurrentWorkflow()
├── updateNodes()                   更新画布节点（自动同步到 currentWorkflow）
└── updateEdges()                   更新画布边
```

## 四、数据流

```
                    HTTP (axios)                    Zustand
用户操作 → 页面组件 →───→  API Client  ──→  后端 API
                    ←───              ←──
                        响应数据           store.setXxx(data)
                                          ↓
                                    页面组件读取 store
                                          ↓
                                    重新渲染
```

前端不直接调用后端 API，统一通过 `src/api/client.ts` 的封装函数：

| API 函数 | 对应后端 | 用途 |
|----------|----------|------|
| `workflowApi.list()` | GET /api/v1/workflows | 获取工作流列表 |
| `workflowApi.get(id)` | GET /api/v1/workflows/:id | 获取单个工作流 |
| `workflowApi.create(wf)` | POST /api/v1/workflows | 创建/保存工作流 |
| `workflowApi.execute(id)` | POST /api/v1/workflows/:id/execute | 执行工作流 |
| `workflowApi.getExecution(id)` | GET /api/v1/workflows/executions/:id | 查询执行结果 |
| `knowledgeApi.search()` | POST /api/v1/knowledge/search | 知识检索 |

## 五、类型定义

前后端共享的核心类型定义在 `src/types/index.ts`，与 backend `core/models.py` 一一对应：

| 前端类型 | 后端模型 |
|----------|----------|
| `Workflow` | `core.models.Workflow` |
| `Node` | `core.models.Node` |
| `Edge` | `core.models.Edge` |
| `Execution` | `core.models.Execution` |

## 六、技术选型确认

| 类别 | 选择 | 原因 |
|------|------|------|
| 框架 | React 18 + TypeScript | 生态最成熟 |
| 构建 | Vite 5 | 快速 HMR |
| UI | Ant Design 5 | 企业级组件库，中文本地化好 |
| 画布 | React Flow 11 | 唯一成熟的工作流画布库 |
| 状态 | Zustand | 轻量、TypeScript 友好 |
| HTTP | Axios | 拦截器、请求取消等开箱即用 |
