# Narrative Engine Cloud - 云端叙事引擎

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置环境变量
```bash
# 设置API密钥（必须）
export API_KEY=your_secret_api_key

# 设置端口（可选，默认5000）
export PORT=5000
```

### 3. 启动服务
```bash
python api.py
```

## API接口

### 健康检查
```bash
GET /health
```

### 初始化引擎
```bash
POST /api/start
Headers: X-API-Key: your_api_key
Body: {
  "npc_name": "沈予曦",
  "profile": "角色设定文本..."
}
```

### 对话
```bash
POST /api/chat
Headers: X-API-Key: your_api_key
Body: {
  "message": "用户消息",
  "history": null  # 可选对话历史
}
```

### 获取状态
```bash
GET /api/state
Headers: X-API-Key: your_api_key
```

### 重置引擎
```bash
POST /api/reset
Headers: X-API-Key: your_api_key
```

## 部署

### Docker部署
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
ENV API_KEY=your_key
EXPOSE 5000
CMD ["python", "api.py"]
```

### Systemd服务（Linux）
创建 `/etc/systemd/system/narrative-engine.service`:
```ini
[Unit]
Description=Narrative Engine Cloud API

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/narrative-engine
Environment="API_KEY=your_key"
ExecStart=/usr/bin/python3 /opt/narrative-engine/api.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## 云端部署后客户端配置

在原型程序中添加切换开关，选择调用本地或云端API。
