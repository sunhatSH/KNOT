KNOT 系统截图指导                                                                                 
                                                                                                    
  以下按页面顺序提供截图指令，可直接交给多模态模型执行。                                            
                                                                                                    
  ---                                                                                               
  截图前准备                                                                                        
                                                                                                    
  # 1. 启动后端                                                                                     
  cd /Users/sunhao/Documents/KNOT/backend                                                           
  .venv/bin/python3 -m uvicorn knot.api.app:create_app --factory --host 0.0.0.0 --port 8000         
                                                                                                    
  # 2. 另开终端，启动前端                                                                           
  cd /Users/sunhao/Documents/KNOT/frontend                                                          
  npm run dev                                                                                       
                                                                  
  浏览器访问 http://localhost:5173                                                                  
  
  ---                                                                                               
  截图清单（共 9 张）                                             
                                                                                                    
  1. 注册页面 /register
                                                                                                    
  - 等待页面完全加载                                                                                
  - 截图: 整个浏览器视口，包含注册表单（用户名、密码、确认密码、注册按钮）
  - 要求: 展示完整的注册表单布局，不要裁剪                                                          
                                                                                                    
  2. 登录页面 /login                                                                                
                                                                                                    
  - 先退出登录（如有），到 /login                                                                   
  - 截图: 整个浏览器视口，包含登录表单（用户名、密码、登录按钮）  
  - 要求: 展示完整的登录页                                                                          
                                                                                                    
  3. 总览工作台 /dashboard                                                                          
                                                                                                    
  - 先登录一个用户                                                                                  
  - 等待 Dashboard 完全加载（统计数据卡片 + 最近执行 + 快捷操作） 
  - 截图: 整个页面，从顶部导航栏到底部                                                              
  - 要求: 展示：导航栏(KNOT logo + 总览/工作流/知识库/监控/设置菜单)、统计卡片(工作流数、执行次数、 
  成功率等)、快捷操作、最近执行列表、最近工作流                                                     
                                                                                                    
  4. 工作流编辑页 /workflows/{id} （新建或已有）                                                    
                                                                  
  - 点击导航栏"工作流"进入列表页，再点击"新建工作流"或"编辑"进入编辑器                              
  - 等待 React Flow 画布完全渲染                                  
  - 截图: 整个页面                                                                                  
  - 要求: 展示：左侧节点面板(node palette:                                                          
  Input/Task/Condition/Loop/Output)、中间画布(已有几个节点用连线连接)、右侧节点配置面板、顶部的 Run 
  按钮和工具栏                                                                                      
                                                                                                    
  5. 工作流编辑器 — 执行中状态                                                                      
   
  - 在编辑器中点击 Run 按钮触发执行                                                                 
  - 等待执行开始（节点出现蓝色脉冲动画、顶部显示执行状态条）      
  - 截图: 立即截图，捕获执行中状态                                                                  
  - 要求: 展示：节点蓝色高亮+脉冲动画、执行状态条("Running..."), 可展开的执行详情面板               
                                                                                                    
  6. 执行详情页 /executions/{id}                                                                    
                                                                                                    
  - 从工作流列表点开一个已完成的执行记录                                                            
  - 截图: 整个页面                                                
  - 要求: 展示：执行状态标签(成功/失败)、执行时间、节点状态概览、Trace/日志列表(按时间顺序显示每个节
  点的开始/完成/耗时)、全局上下文数据                                                               
                                                                                                    
  7. 知识库页面 /knowledge                                                                          
                                                                  
  - 点击导航栏"知识库"                                                                              
  - 如果已有文档则展示列表，如果没有则展示空状态                  
  - 截图: 整个页面                                                                                  
  - 要求: 展示：搜索栏+筛选条件(文件类型、日期)、文档列表(支持分页)、Collection管理、上传区域(拖拽上
  传)、最好有2-3个文档展示                                                                          
                                                                                                    
  8. 监控面板 /monitoring                                                                           
                                                                  
  - 必须已有至少一次工作流执行记录                                                                  
  - 点击导航栏"监控"                                              
  - 等待监控数据加载（统计卡片+图表+表格）                                                          
  - 截图: 整个页面                                                                                  
  - 要求: 展示：统计卡片行(总执行数、成功率、平均耗时、失败数)、状态分布可视化条、近7天执行趋势图、 
  最近执行表格(时间/工作流/状态/耗时)、最慢节点表格                                                 
                                                                  
  9. 设置页面 /settings                                                                             
                                                                  
  - 点击导航栏"设置"                                                                                
  - 截图: 整个页面                                                
  - 要求: 展示：用户信息、亮色/暗色主题切换、语言切换(中/EN)                                        
                                                                                                    
  ---                                                                                               
  截图技术参数                                                                                      
                                                                                                    
  - 工具: 使用 Playwright 或 Puppeteer 的 page.screenshot({ fullPage: true })
  - 分辨率: 1440×900 或以上                                                                         
  - 浏览器: Chromium                                                                                
  - 等待: 每次导航后 page.waitForSelector() 确认页面渲染完成                                        
  - 如果拿不到数据: 先用 API 创建测试数据（见下方）                                                 
                                                                                                    
  准备测试数据 (可选，让截图更丰富)                                                                 
                                                                                                    
  # 注册用户                                                                                        
  curl -X POST http://localhost:8000/api/v1/auth/register \       
    -H "Content-Type: application/json" \                                                           
    -d '{"username":"demo","password":"demo123","email":"demo@knot.dev"}'                           
                                                                                                    
  # 登录获取token                                                                                   
  TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \                                 
    -H "Content-Type: application/json" \                                                           
    -d '{"username":"demo","password":"demo123"}' | python3 -c "import 
  sys,json;print(json.load(sys.stdin)['access_token'])")                                            
                                                                  
  # 创建工作流                                                                                      
  curl -X POST http://localhost:8000/api/v1/workflows \           
    -H "Content-Type: application/json" \                                                           
    -H "Authorization: Bearer $TOKEN" \                                                             
    -d '{"name":"数据分析流水线","nodes":[{"id":"n1","type":"input","label":"输入"},{"id":"n2","type
  ":"task","label":"数据采集","config":{"agent_role":"researcher"}},{"id":"n3","type":"task","label"
  :"分析报告","config":{"agent_role":"coder"}},{"id":"n4","type":"output","label":"输出"}],"edges":[
  {"source_id":"n1","target_id":"n2"},{"source_id":"n2","target_id":"n3"},{"source_id":"n3","target_
  id":"n4"}]}'                                                    

  ---
  注意事项: 截图要用 fullPage: true 截全页面，不要只截视口；每个页面前先等待所有 API 请求完成(可
  waitForTimeout(2000) 兜底)。