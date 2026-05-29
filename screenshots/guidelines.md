# KNOT 系统截图指导

以下按页面顺序提供截图指令，可直接交给多模态模型执行。

---

## 截图前准备

```bash
# 1. 启动后端
cd /Users/sunhao/Documents/KNOT/backend
.venv/bin/python3 -m uvicorn knot.api.app:create_app --factory --host 0.0.0.0 --port 8000

# 2. 另开终端，启动前端
cd /Users/sunhao/Documents/KNOT/frontend
npm run dev
```

浏览器访问 `http://localhost:5173`

---

## 准备测试数据

```bash
# 注册用户
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"demo123","email":"demo@knot.dev"}'

# 登录获取token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"demo123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 创建工作流1: 数据分析流水线
curl -X POST http://localhost:8000/api/v1/workflows \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"数据分析流水线","nodes":[{"id":"n1","type":"input","label":"输入"},{"id":"n2","type":"task","label":"数据采集","config":{"agent_role":"researcher"}},{"id":"n3","type":"task","label":"分析报告","config":{"agent_role":"coder"}},{"id":"n4","type":"output","label":"输出"}],"edges":[{"source_id":"n1","target_id":"n2"},{"source_id":"n2","target_id":"n3"},{"source_id":"n3","target_id":"n4"}]}'

# 创建工作流2: 客户支持
curl -X POST http://localhost:8000/api/v1/workflows \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"客户支持问答","nodes":[{"id":"i1","type":"input","label":"问题输入"},{"id":"i2","type":"task","label":"知识检索","config":{"knowledge_enabled":true}},{"id":"i3","type":"output","label":"回答"}],"edges":[{"source_id":"i1","target_id":"i2"},{"source_id":"i2","target_id":"i3"}]}'

# 创建工作流3: 多智能体辩论
curl -X POST http://localhost:8000/api/v1/workflows \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"多智能体辩论","nodes":[{"id":"d1","type":"input","label":"议题"},{"id":"d2","type":"task","label":"辩论","config":{"multi_agent_mode":"debate","max_debate_rounds":3}},{"id":"d3","type":"output","label":"共识"}],"edges":[{"source_id":"d1","target_id":"d2"},{"source_id":"d2","target_id":"d3"}]}'
```

---

## 截图清单

### 1. 注册页面 `/register`

- 等待页面完全加载
- **截图**: 整个浏览器视口，包含注册表单（用户名、密码、确认密码、注册按钮、底部登录链接）
- **要求**: 展示完整的注册表单布局和页面结构，不要裁剪

---

### 2. 登录页面 `/login`

- 先退出登录（如有），导航到 `/login`
- **截图**: 整个浏览器视口，包含登录表单（用户名、密码、登录按钮、底部注册链接）
- **要求**: 展示完整的登录页

---

### 3. 总览工作台 `/dashboard` — 有数据状态

- 先登录 demo 用户（用户名: demo, 密码: demo123）
- 等待 Dashboard 完全加载（统计数据卡片 + 最近执行 + 快捷操作区域）
- **截图**: 整个页面，从顶部导航栏到底部
- **要求**: 必须展示：导航栏(KNOT logo + 总览/工作流/知识库/监控/设置五个菜单项)、统计卡片行(工作流数 3+、执行次数、成功率、24h 活跃度)、快捷操作卡片行(新建工作流/AI生成/上传知识/设置)、最近执行列表、最近工作流网格

---

### 4. 工作流列表页 `/workflows` — 有数据状态

- 点击导航栏"工作流" 或直接导航到 `/workflows`
- 等待工作流卡片网格完全渲染
- **截图**: 整个页面
- **要求**: 展示：上方"工作流"标题、右侧"从模板创建"按钮 + 蓝色"新建工作流"按钮、下方的卡片网格(每张卡片展示工作流名称、描述、节点数标签、标签tag)，至少 3 张卡片

---

### 5. 工作流列表页 `/workflows` — 空状态

- 先清空数据或用一个新注册的空白用户
- 导航到 `/workflows`
- **截图**: 整个页面
- **要求**: 展示：中间大图标 + "暂无工作流，点击上方按钮创建" 提示文字 + 上方工具栏(新建/从模板创建按钮)

---

### 6. 模板选择器弹窗

- 在工作流列表页 `/workflows` 点击"从模板创建"按钮
- 等待弹窗加载完成，模板卡片网格出现
- **截图**: 整个弹窗模态框（背景可以半透明变暗）
- **要求**: 展示：弹窗标题"选择模板"、分类标签页(All/Data Processing/Customer Service/Multi-Agent/Monitoring)、搜索框、卡片网格(每张卡片含名称/描述/分类tag/节点数/使用次数)，至少显示 4-5 个模板卡片

---

### 7. 工作流编辑页 `/workflows/{id}` — 画布编辑状态

- 点击第一张工作流卡片进入编辑器
- 等待 React Flow 画布完全渲染（节点 + 连线可见）
- 如果画布为空，从左侧 NodePalette 拖拽 2-3 个节点到画布并连接
- **截图**: 整个页面
- **要求**: 展示：顶部工具栏(KNOT 导航 + 页面标题 + Run 执行按钮)、左侧节点面板(Input/Task/Condition/Loop/Output 五种节点类型)、中间画布(节点已排列并用箭头连线连接)、右侧可配置属性面板(选中节点后显示)、右下角版本历史入口

---

### 8. 工作流编辑器 — 执行中状态

- 在编辑器中点击 Run 按钮触发工作流执行
- 等待 1-2 秒，节点出现蓝色脉冲动画、顶部显示执行状态条
- **截图**: 立即截图，捕获执行中状态
- **要求**: 展示：节点蓝色边框+脉冲呼吸动画、顶部蓝色执行状态条(显示 "Running..." + Spin 图标 + 执行ID)、右侧展开的执行控制面板(包含 Pause/Resume/Cancel 按钮 + 执行进度 + Trace 日志列表)

---

### 9. 工作流编辑器 — 版本历史弹窗

- 在编辑器中点击版本历史入口（通常是个时钟图标或按钮）
- 等待版本列表弹窗加载
- **截图**: 版本历史弹窗模态框
- **要求**: 展示：弹窗标题"版本历史"、Timeline 时间线列表(每次保存记录含版本号、保存时间、保存人、备注信息)、底部"恢复"按钮

---

### 10. 工作流编辑器 — 智能体配置面板

- 在编辑器选中一个 TASK 类型节点
- 展开右侧 AgentConfigPanel
- **截图**: 右侧配置面板区域
- **要求**: 展示：执行模式选择(单智能体/并行/辩论)、智能体团队列表(每个智能体含名称/角色标签)、参数配置(温度、最大轮数等)

---

### 11. 执行详情页 `/executions/{id}`

- 从工作流列表点开一个已完成的执行记录（或从菜单找执行入口）
- 等待详情页完全加载
- **截图**: 整个页面
- **要求**: 展示：执行状态标签(如绿色"success"或红色"failed")、执行ID(可复制)、起止时间、总耗时、节点状态概览(每个节点的成功/失败/跳过标签)、Trace 时间线(按时间顺序显示每个节点的开始→完成事件、耗时毫秒数)、全局上下文数据区域

---

### 12. 知识库页面 `/knowledge` — 有数据状态

- 点击导航栏"知识库"
- 先上传 1-2 个文档（通过上传区域拖入 `.txt` 或 `.md` 文件）
- 等待文档上传完成并出现在文档列表中
- **截图**: 整个页面
- **要求**: 展示：上方"知识库"标题 + "文档"和"Collections"两个标签页、文档标签页下：搜索栏+筛选行(文件类型下拉、日期输入)、文档列表(每行显示文档名/类型标签/大小/上传时间/分页器)、右侧或上方上传区域(虚线边框拖拽上传区域 + 上传按钮)、列表中至少 2 条文档记录

---

### 13. 知识库页面 `/knowledge` — 文档预览弹窗

- 在文档列表中点击一条文档
- 等待预览弹窗加载
- **截图**: 文档预览弹窗模态框
- **要求**: 展示：弹窗标题(文档名称)、元数据表格(ID/Collection/类型/大小/Chunk数/上传时间)、内容预览区域(文档前几段文本)

---

### 14. 监控面板 `/monitoring`

- 必须先执行过至少一次工作流（这样才有统计数据）
- 点击导航栏"监控"
- 等待监控数据加载
- **截图**: 整个页面
- **要求**: 展示：顶部统计卡片行(总执行数/成功率百分比/平均耗时/失败数)、状态分布可视化(横向堆叠条形图，含成功/失败/运行中比例)、近7天执行趋势图(每日执行次数的柱状或折线图)、最近执行表格(时间/工作流ID/状态彩色标签/耗时/错误信息)、最慢节点表格(节点名/平均耗时/总耗时/调用次数)

---

### 15. 设置页面 `/settings` — 亮色模式

- 点击导航栏"设置"
- 确保当前为亮色主题
- **截图**: 整个页面
- **要求**: 展示：标题"设置"、用户信息卡片(用户名/邮箱/角色)、主题切换开关(亮色/暗色 RadioGroup)、语言切换(中文/English)

---

### 16. 暗色模式切换

- 在设置页面点击切换为**暗色模式**，或点击顶部导航栏的月亮图标
- 等待主题切换动画完成
- **截图**: 工作流列表页 `/workflows` 在暗色模式下的全页
- **要求**: 页面背景为深色、卡片为深色背景、文字为浅色、整体展示暗色主题风格

---

### 17. 英文界面

- 在设置页或点击顶部导航栏的"EN"语言切换按钮
- 等待界面语言切换为英文
- **截图**: 总览工作台 `/dashboard` 的英文界面全页
- **要求**: 所有界面文字为英文：导航菜单(Dashboard/Workflows/Knowledge/Monitoring/Settings)、统计卡片标签、按钮文字

---

### 18. 错误/通知状态

- 在知识库页面 `/knowledge` 点击搜索
- 使用开发者工具将网络断开（`Offline` 模式）
- 触发一个 API 请求（如搜索、刷新列表）
- **截图**: 页面顶部出现的红色错误 Alert 通知
- **要求**: 展示：错误提示 Alert 组件(含错误描述 + 关闭按钮)、页面其余部分保持正常

---

## 截图技术参数

- **工具**: 使用 Playwright 或 Puppeteer 的 `page.screenshot({ fullPage: true })`
- **分辨率**: 1440×900 或以上
- **浏览器**: Chromium
- **等待策略**:
  - 每次导航后: `page.waitForSelector('main, .ant-layout-content', { timeout: 10000 })`
  - 弹窗: `page.waitForSelector('.ant-modal', { visible: true })`
  - 数据加载: `page.waitForSelector('.ant-spin-spinning', { state: 'detached' })` 等待 Spin 消失
  - 兜底: 每个页面 `page.waitForTimeout(2000)`

## 特殊说明

- **空状态截图**（#5）：建议在全新安装或新建用户后截取
- **有数据截图**（#3, #4, #12, #14）：必须先在准备数据阶段用 curl 创建好工作流
- **暗色模式**（#16）：截完所有亮色截图后统一切换暗色模式再截
- **英文界面**（#17）：在暗色模式截图之后切换语言，避免重复截亮色
- 所有截图请用 `fullPage: true`，不要只截浏览器视口
- 如果弹窗被背景遮挡，可调低背景透明度或直接截弹窗区域
