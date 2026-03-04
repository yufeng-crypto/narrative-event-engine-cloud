# 云端 Web 测试工具部署说明

## 概述
Web 测试工具是一个 Flask Web 应用，提供浏览器界面来测试云端叙事引擎 API。

## 部署信息
- **云端引擎 API**: http://8.134.212.37:80 (已部署)
- **Web 测试工具端口**: 8080

## 部署步骤

### 1. 环境准备
确保服务器已安装 Python 3.x 和依赖：
```bash
pip install flask requests
```

### 2. 获取代码
```bash
git clone https://github.com/yufeng-crypto/narrative-event-engine-cloud.git
cd narrative-event-engine-cloud
git checkout feature/web-test-tool
```

### 3. 配置环境变量（生产环境必须设置）
```bash
# 设置 API 密钥（生产环境必须设置）
export API_KEY="your-secure-api-key"

# 可选：设置 Flask 密钥
export SECRET_KEY="your-secret-key"

# 可选：设置云端引擎地址（默认 http://8.134.212.37:80）
export CLOUD_ENGINE_URL="http://8.134.212.37:80"

# 可选：明确标记为生产环境
export FLASK_ENV=production
export PRODUCTION=true
```

### 4. 启动服务

#### 开发模式
```bash
python web_app.py
# 服务将在 http://0.0.0.0:8080 启动
```

#### 生产模式（推荐使用 gunicorn）
```bash
# 安装 gunicorn
pip install gunicorn

# 启动服务
gunicorn -w 4 -b 0.0.0.0:8080 web_app:app
```

### 5. 使用方式
1. 打开浏览器访问：http://<server-ip>:8080
2. 选择或输入 NPC 角色
3. 点击"启动引擎"
4. 在对话框中输入消息进行测试

## API 端点说明

### Web 界面 API（需 CSRF 认证）
- `POST /api/web/start` - 启动引擎
- `POST /api/web/chat` - 发送对话
- `GET /api/web/state` - 获取状态
- `POST /api/web/reset` - 重置引擎

### 云端引擎 API（需 API Key 认证）
- `POST /api/start` - 启动引擎
- `POST /api/chat` - 发送对话
- `GET /api/state` - 获取状态
- `POST /api/reset` - 重置引擎

## 安全注意事项
1. **生产环境必须设置 API_KEY 环境变量**
2. **生产环境必须设置 SECRET_KEY 环境变量**
3. 禁用默认或不安全的密钥值
4. 建议使用 HTTPS 访问（配置 Nginx 反向代理）

## 故障排除
- 检查云端引擎是否运行：`curl http://8.134.212.37:80/health`
- 检查日志输出：`tail -f logs/session_*.log`
