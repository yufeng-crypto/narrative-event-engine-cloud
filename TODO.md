# Web 测试工具开发任务列表

## 项目信息
- 分支：feature/web-test-tool
- 工作目录：logic/engine-cloud/
- 云端引擎API：http://8.134.212.37:80

## 任务列表

### Task 1: Flask Web 服务基础框架搭建
- [ ] 创建 Flask 应用基础结构 (web_app.py)
- [ ] 配置静态文件目录 (static/)
- [ ] 配置模板目录 (templates/)
- [ ] 实现主页路由 (/)
- [ ] 配置云端引擎 API 地址

### Task 2: 前端页面 - 对话界面
- [ ] 角色选择下拉框
- [ ] 对话窗口（显示历史消息）
- [ ] 消息输入框
- [ ] 发送按钮
- [ ] 六轴状态显示区域
- [ ] 事件卡显示区域

### Task 3: 前端页面 - 调试标签页
- [ ] 四个调试标签页：Perception / Director / Predictor / Performer
- [ ] 每个标签页显示【输入】和【输出】两个窗口
- [ ] 输入窗口：发送给 LLM 的完整 prompt
- [ ] 输出窗口：LLM 返回的原始内容

### Task 4: 后端 API - 引擎对接
- [x] POST /api/start - 初始化引擎
- [x] POST /api/chat - 对话接口
- [x] GET /api/state - 获取状态
- [x] POST /api/reset - 重置引擎
- [x] 会话管理（支持多用户）
- [x] GET /api/session - 获取会话信息

### Task 5: 前端交互逻辑
- [ ] 发送消息逻辑
- [ ] 轮询获取对话结果
- [ ] 对话历史显示
- [ ] 六轴实时更新
- [ ] 事件卡显示

### Task 6: 测试与部署
- [ ] 本地测试
- [ ] 部署到云端服务器
- [ ] 调试日志系统

## 参考文档
- GUI原型程序：docs/PROTOTYPE.md
- 引擎核心逻辑：docs/ENGINE_CORE.md
- 云端引擎API：logic/engine-cloud/api.py
