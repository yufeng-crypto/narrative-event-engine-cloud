# Narrative Engine Cloud API
# 云端叙事引擎API服务

from flask import Flask, request, jsonify
from engine_llm import create_engine, start_engine, chat, get_state
import os

app = Flask(__name__)

# 全局引擎实例
engine = None

# API认证Key（从环境变量读取）
API_KEY = os.environ.get('API_KEY', 'default_key_change_me')


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
@require_auth
def start():
    """初始化引擎"""
    global engine
    data = request.json
    
    npc_name = data.get('npc_name', 'default')
    profile = data.get('profile', '')
    
    engine = create_engine()
    start_engine(engine, npc_name=npc_name, profile=profile)
    
    return jsonify({
        "status": "ok",
        "message": f"Engine started for {npc_name}",
        "npc_name": npc_name
    })


@app.route('/api/chat', methods=['POST'])
@require_auth
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
    
    return jsonify(result)


@app.route('/api/state', methods=['GET'])
@require_auth
def state_api():
    """获取引擎状态"""
    if engine is None:
        return jsonify({"error": "Engine not initialized"}), 400
    
    state = get_state(engine)
    return jsonify(state)


@app.route('/api/reset', methods=['POST'])
@require_auth
def reset_api():
    """重置引擎"""
    global engine
    engine = None
    return jsonify({"status": "ok", "message": "Engine reset"})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
