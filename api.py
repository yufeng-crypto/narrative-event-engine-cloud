# Narrative Engine Cloud API
# 云端叙事引擎API服务

from flask import Flask, request, jsonify
from engine_llm import create_engine, start_engine, chat, get_state
import os
import json
from datetime import datetime
from pathlib import Path
import secrets

app = Flask(__name__)

# 全局引擎实例
engine = None

# API认证Key（从环境变量读取）- 生产环境必须设置
API_KEY = os.environ.get('API_KEY')
if not API_KEY:
    print("WARNING: API_KEY not set. Set environment variable API_KEY for production.")
    # 开发环境使用随机密钥
    API_KEY = f"dev_key_{secrets.token_hex(8)}"

# 日志目录
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 当前会话日志文件
session_log_file = None


def get_session_log_file():
    """获取当前会话日志文件路径"""
    global session_log_file
    if session_log_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_log_file = LOG_DIR / f"session_{timestamp}.log"
    return session_log_file


def log_request(endpoint, request_data, response_data, status_code=200):
    """记录请求到日志文件"""
    log_file = get_session_log_file()
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "endpoint": endpoint,
        "request": request_data,
        "response": response_data,
        "status": status_code
    }
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    return log_file


def require_auth(f):
    """API认证装饰器"""
    def wrapper(*args, **kwargs):
        auth_key = request.headers.get('X-API-Key')
        if auth_key != API_KEY:
            return jsonify({"error": "Unauthorized", "message": "Invalid API Key"}), 401
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({"status": "ok", "engine": "ready" if engine else "not_initialized"})


@app.route('/api/start', methods=['POST'])
# @require_auth  # 临时注释掉认证
def start():
    """初始化引擎"""
    global engine
    data = request.json
    
    npc_name = data.get('npc_name', 'default')
    profile = data.get('profile', '')
    
    engine = create_engine()
    start_engine(engine, npc_name=npc_name, profile=profile)
    
    response = {
        "status": "ok",
        "message": f"Engine started for {npc_name}",
        "npc_name": npc_name
    }
    
    log_request("/api/start", data, response)
    
    return jsonify(response)


@app.route('/api/chat', methods=['POST'])
# @require_auth  # 临时注释掉认证
def chat_api():
    """对话接口"""
    if engine is None:
        return jsonify({"error": "Engine not initialized", "message": "Please call /api/start first"}), 400
    
    data = request.json
    user_message = data.get('message', '')
    conversation_history = data.get('history', None)
    
    if not user_message:
        return jsonify({"error": "Empty message", "message": "message is required"}), 400
    
    result = chat(engine, user_message, conversation_history)
    
    # 记录完整日志（包括三个模块的输入输出）
    log_data = {
        "message": user_message,
        "history": conversation_history
    }
    
    # 记录完整的各模块输入输出
    log_result = {
        "round": result.get("round", 0),
        "user": result.get("user", ""),
        "npc": result.get("npc", ""),
        "axes": result.get("axes", {}),
        # Perception模块
        "perception_input": result.get("perception_input", ""),
        "perception_output": result.get("perception_output", {}),
        "perception_raw_output": result.get("perception_raw_output", ""),
        # Predictor模块
        "predictor_input": result.get("predictor_input", ""),
        "predictor_output": result.get("predictor_output", {}),
        "predictor_raw_output": result.get("predictor_raw_output", ""),
        # Director模块
        "director_input": result.get("director_input", ""),
        "director_output": result.get("director_output", ""),
        "director_raw_output": result.get("director_raw_output", ""),
        # Performer模块
        "performer_input": result.get("performer_input", ""),
        "performer_output": result.get("performer_output", ""),
        "performer_raw_output": result.get("performer_raw_output", ""),
        # 其他信息
        "timing": result.get("timing", {}),
        "story_patch": result.get("story_patch", ""),
    }
    log_request("/api/chat", log_data, log_result)
    
    return jsonify(result)


@app.route('/api/state', methods=['GET'])
# @require_auth  # 临时注释掉认证
def state_api():
    """获取引擎状态"""
    if engine is None:
        return jsonify({"error": "Engine not initialized"}), 400
    
    state = get_state(engine)
    log_request("/api/state", {}, state)
    return jsonify(state)


@app.route('/api/reset', methods=['POST'])
# @require_auth  # 临时注释掉认证
def reset_api():
    """重置引擎"""
    global engine
    engine = None
    response = {"status": "ok", "message": "Engine reset"}
    log_request("/api/reset", {}, response)
    return jsonify(response)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"日志将保存到: {LOG_DIR}")
    app.run(host='0.0.0.0', port=port, debug=False)
