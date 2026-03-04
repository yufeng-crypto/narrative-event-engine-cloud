# Web App - Flask Web Interface for Narrative Engine Cloud
# Web版原型程序 - 调用云端叙事引擎API

import os
import re
import json
import secrets
import time
import requests
from functools import lru_cache
from flask import Flask, render_template, request, jsonify, session, make_response
from pathlib import Path

app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')

# ============ 密钥安全检查 ============
# 检测是否为生产环境
def _is_production():
    """判断是否运行在生产环境"""
    # 检查 FLASK_ENV 环境变量，或者根据端口判断
    env = os.environ.get('FLASK_ENV', '').lower()
    if env == 'production':
        return True
    # 如果未明确设置环境，检查是否有生产环境特征
    # 例如：非调试模式 + 非本地地址
    debug = os.environ.get('FLASK_DEBUG', '').lower()
    return debug == 'false' and os.environ.get('PRODUCTION', '').lower() == 'true'

# 配置密钥 - 生产环境必须使用环境变量
_secret_key = os.environ.get('SECRET_KEY')
if _secret_key is None:
    if _is_production():
        raise ValueError("SECRET_KEY environment variable must be set in production!")
    else:
        # 开发环境使用随机密钥
        _secret_key = secrets.token_hex(32)
        print("WARNING: Using random secret key for development. Set SECRET_KEY for persistence.")
elif _secret_key in ('dev_secret_key_change_in_production', 'change_me', ''):
    if _is_production():
        raise ValueError("Default/unsafe SECRET_KEY cannot be used in production!")
    # 隐藏敏感信息
    _secret_key = None
    print("WARNING: Invalid SECRET_KEY detected. Authentication may fail.")

app.secret_key = _secret_key if _secret_key else secrets.token_hex(32)

# ============ CSRF 保护 ============
CSRF_TOKEN_NAME = 'csrf_token'
CSRF_TOKEN_EXPIRY = 3600  # 1小时

def generate_csrf_token():
    """生成 CSRF token"""
    if CSRF_TOKEN_NAME not in session:
        session[CSRF_TOKEN_NAME] = secrets.token_hex(32)
        session[f'{CSRF_TOKEN_NAME}_time'] = time.time()
    # 检查是否过期
    token_time = session.get(f'{CSRF_TOKEN_NAME}_time', 0)
    if time.time() - token_time > CSRF_TOKEN_EXPIRY:
        session[CSRF_TOKEN_NAME] = secrets.token_hex(32)
        session[f'{CSRF_TOKEN_NAME}_time'] = time.time()
    return session[CSRF_TOKEN_NAME]

def validate_csrf_token(token):
    """验证 CSRF token"""
    if not token:
        return False
    session_token = session.get(CSRF_TOKEN_NAME)
    return secrets.compare_digest(token, session_token)

# 注册 CSRF token 生成器
app.jinja_env.globals['csrf_token'] = generate_csrf_token

# ============ API认证Key（从环境变量读取）============
_api_key = os.environ.get('API_KEY')
if _api_key is None:
    if _is_production():
        raise ValueError("API_KEY environment variable must be set in production!")
    else:
        _api_key = f"dev_key_{secrets.token_hex(8)}"
        print("WARNING: Using random API key for development. Set API_KEY for persistence.")
elif _api_key in ('default_key_change_me', 'change_me', ''):
    if _is_production():
        raise ValueError("Default/unsafe API_KEY cannot be used in production!")
    # 隐藏敏感信息
    _api_key = None
    print("WARNING: Invalid API_KEY detected. API calls may fail.")

API_KEY = _api_key if _api_key else f"dev_key_{secrets.token_hex(8)}"

# ============ 会话管理 ============
# 使用独立的会话存储，支持多用户
# 格式: {session_id: {"engine_started": bool, "npc_name": str, "conversation_history": list, "last_access": timestamp}}
_sessions = {}

# 会话过期时间（秒）- 30分钟
SESSION_EXPIRY_SECONDS = 30 * 60

# 会话ID格式验证正则：16-64字符，只允许字母数字
SESSION_ID_PATTERN = re.compile(r'^[a-zA-Z0-9]{16,64}$')

def _cleanup_expired_sessions():
    """清理过期会话"""
    current_time = time.time()
    expired = [
        sid for sid, data in _sessions.items()
        if current_time - data.get("last_access", 0) > SESSION_EXPIRY_SECONDS
    ]
    for sid in expired:
        del _sessions[sid]
    return len(expired)

def _validate_session_id(session_id: str) -> bool:
    """验证会话ID格式"""
    if not session_id or not isinstance(session_id, str):
        return False
    return bool(SESSION_ID_PATTERN.match(session_id))

def get_session_id():
    """获取当前会话ID（从header或cookie）"""
    # 优先从自定义header获取，支持API调用场景
    session_id = request.headers.get('X-Session-ID')
    if session_id and _validate_session_id(session_id):
        return session_id
    
    # 其次从cookie获取（Web场景）
    session_id = request.cookies.get('session_id')
    if session_id and _validate_session_id(session_id):
        return session_id
    
    # 生成新的会话ID（16字节hex = 32字符）
    new_id = secrets.token_hex(16)
    # 验证生成的ID符合格式
    while not _validate_session_id(new_id):
        new_id = secrets.token_hex(16)
    return new_id

def get_session_data(session_id):
    """获取会话数据"""
    # 清理过期会话（每次获取时检查）
    _cleanup_expired_sessions()
    
    if session_id not in _sessions:
        _sessions[session_id] = {
            "engine_started": False,
            "npc_name": None,
            "conversation_history": [],
            "last_access": time.time()
        }
    else:
        # 更新最后访问时间
        _sessions[session_id]["last_access"] = time.time()
    return _sessions[session_id]

def update_session_data(session_id, data):
    """更新会话数据"""
    # 清理过期会话（每次更新时检查）
    _cleanup_expired_sessions()
    
    if session_id not in _sessions:
        _sessions[session_id] = {
            "engine_started": False,
            "npc_name": None,
            "conversation_history": [],
            "last_access": time.time()
        }
    _sessions[session_id].update(data)
    _sessions[session_id]["last_access"] = time.time()

def clear_session_data(session_id):
    """清除会话数据"""
    if session_id in _sessions:
        del _sessions[session_id]

# ============ 云端引擎配置 ============
CLOUD_ENGINE_URL = os.environ.get('CLOUD_ENGINE_URL', 'http://127.0.0.1:5000')

# API端点
API_START = f"{CLOUD_ENGINE_URL}/api/start"
API_CHAT = f"{CLOUD_ENGINE_URL}/api/chat"
API_STATE = f"{CLOUD_ENGINE_URL}/api/state"
API_RESET = f"{CLOUD_ENGINE_URL}/api/reset"
API_HEALTH = f"{CLOUD_ENGINE_URL}/health"


def get_api_headers():
    """获取API请求头"""
    return {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json'
    }


def safe_json_response(response):
    """安全解析 response.json()，捕获 JSON 解析异常"""
    try:
        return response.json()
    except json.JSONDecodeError as e:
        # 返回错误信息而不是崩溃
        return {"error": "Invalid JSON response", "message": str(e)}


def check_engine_health():
    """检查云端引擎健康状态"""
    try:
        response = requests.get(API_HEALTH, timeout=5)
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        return None


# ============ 路由 ============

@app.route('/')
def index():
    """主页"""
    # 检查引擎状态
    engine_status = check_engine_health()
    return render_template('index.html', engine_status=engine_status)


@app.route('/api/web/start', methods=['POST'])
def web_start():
    """Web端 - 初始化引擎"""
    # CSRF 验证
    csrf_token = request.headers.get('X-CSRF-Token') or request.json.get('csrf_token')
    if not validate_csrf_token(csrf_token):
        return jsonify({"error": "CSRF token validation failed"}), 403
    
    data = request.json
    npc_name = data.get('npc_name', 'default')
    profile = data.get('profile', '')
    
    try:
        response = requests.post(
            API_START,
            json={'npc_name': npc_name, 'profile': profile},
            headers=get_api_headers(),
            timeout=30
        )
        
        if response.status_code == 200:
            result = safe_json_response(response)
            session['engine_started'] = True
            session['npc_name'] = npc_name
            return jsonify(result)
        else:
            error_result = safe_json_response(response)
            return jsonify(error_result), response.status_code
            
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Connection failed", "message": str(e)}), 500


@app.route('/api/web/chat', methods=['POST'])
def web_chat():
    """Web端 - 对话接口"""
    # CSRF 验证
    csrf_token = request.headers.get('X-CSRF-Token') or request.json.get('csrf_token')
    if not validate_csrf_token(csrf_token):
        return jsonify({"error": "CSRF token validation failed"}), 403
    
    if not session.get('engine_started'):
        return jsonify({"error": "Engine not initialized"}), 400
    
    data = request.json
    user_message = data.get('message', '')
    conversation_history = data.get('history', None)
    
    if not user_message:
        return jsonify({"error": "Empty message"}), 400
    
    try:
        response = requests.post(
            API_CHAT,
            json={'message': user_message, 'history': conversation_history},
            headers=get_api_headers(),
            timeout=60
        )
        
        if response.status_code == 200:
            result = safe_json_response(response)
            return jsonify(result)
        else:
            error_result = safe_json_response(response)
            return jsonify(error_result), response.status_code
            
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Connection failed", "message": str(e)}), 500


@app.route('/api/web/state', methods=['GET'])
def web_state():
    """Web端 - 获取引擎状态"""
    try:
        response = requests.get(
            API_STATE,
            headers=get_api_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            result = safe_json_response(response)
            return jsonify(result)
        else:
            error_result = safe_json_response(response)
            return jsonify(error_result), response.status_code
            
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Connection failed", "message": str(e)}), 500


@app.route('/api/web/reset', methods=['POST'])
def web_reset():
    """Web端 - 重置引擎"""
    # CSRF 验证
    csrf_token = request.headers.get('X-CSRF-Token') or request.json.get('csrf_token')
    if not validate_csrf_token(csrf_token):
        return jsonify({"error": "CSRF token validation failed"}), 403
    
    try:
        response = requests.post(
            API_RESET,
            headers=get_api_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            session.clear()
            result = safe_json_response(response)
            return jsonify(result)
        else:
            error_result = safe_json_response(response)
            return jsonify(error_result), response.status_code
            
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Connection failed", "message": str(e)}), 500


# ============ Task 4: 后端 API - 引擎对接 ============
# 提供标准化的 /api/* 接口，支持多用户会话管理

@app.route('/api/start', methods=['POST'])
def api_start():
    """API端 - 初始化引擎
    
    请求头:
        X-API-Key: API认证密钥
        X-Session-ID: 会话ID（可选，用于多用户支持）
    
    请求体:
        {
            "npc_name": "NPC名称",
            "profile": "NPC角色设定"
        }
    
    响应:
        {
            "status": "ok",
            "message": "Engine started for {npc_name}",
            "npc_name": "{npc_name}",
            "session_id": "会话ID"
        }
    """
    # 验证 API Key
    auth_key = request.headers.get('X-API-Key')
    if auth_key != API_KEY:
        return jsonify({"error": "Unauthorized", "message": "Invalid API Key"}), 401
    
    data = request.json or {}
    npc_name = data.get('npc_name', 'default')
    profile = data.get('profile', '')
    
    # 获取或创建会话
    session_id = get_session_id()
    
    try:
        response = requests.post(
            API_START,
            json={'npc_name': npc_name, 'profile': profile},
            headers=get_api_headers(),
            timeout=30
        )
        
        if response.status_code == 200:
            result = safe_json_response(response)
            # 更新会话状态
            update_session_data(session_id, {
                "engine_started": True,
                "npc_name": npc_name,
                "conversation_history": []
            })
            result["session_id"] = session_id
            return jsonify(result)
        else:
            error_result = safe_json_response(response)
            return jsonify(error_result), response.status_code
            
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Connection failed", "message": str(e)}), 500


@app.route('/api/chat', methods=['POST'])
def api_chat():
    """API端 - 对话接口
    
    请求头:
        X-API-Key: API认证密钥
        X-Session-ID: 会话ID（必需，用于多用户支持）
    
    请求体:
        {
            "message": "用户消息",
            "history": ["历史对话"]  // 可选
        }
    
    响应:
        {
            "round": 1,
            "user": "用户消息",
            "npc": "NPC回复",
            "axes": {...},
            // ... 其他调试信息
        }
    """
    # 验证 API Key
    auth_key = request.headers.get('X-API-Key')
    if auth_key != API_KEY:
        return jsonify({"error": "Unauthorized", "message": "Invalid API Key"}), 401
    
    # 获取会话
    session_id = get_session_id()
    session_data = get_session_data(session_id)
    
    if not session_data.get('engine_started'):
        return jsonify({
            "error": "Engine not initialized", 
            "message": "Please call /api/start first",
            "session_id": session_id
        }), 400
    
    data = request.json or {}
    user_message = data.get('message', '')
    conversation_history = data.get('history', None)
    
    if not user_message:
        return jsonify({"error": "Empty message", "message": "message is required"}), 400
    
    try:
        response = requests.post(
            API_CHAT,
            json={'message': user_message, 'history': conversation_history},
            headers=get_api_headers(),
            timeout=60
        )
        
        if response.status_code == 200:
            result = safe_json_response(response)
            # 更新会话历史
            history = session_data.get('conversation_history', [])
            history.append({"role": "user", "content": user_message})
            if result.get("npc"):
                history.append({"role": "npc", "content": result["npc"]})
            update_session_data(session_id, {"conversation_history": history})
            result["session_id"] = session_id
            return jsonify(result)
        else:
            error_result = safe_json_response(response)
            return jsonify(error_result), response.status_code
            
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Connection failed", "message": str(e)}), 500


@app.route('/api/state', methods=['GET'])
def api_state():
    """API端 - 获取引擎状态
    
    请求头:
        X-API-Key: API认证密钥
        X-Session-ID: 会话ID（可选）
    
    响应:
        {
            "axes": {...},
            "event_cards": [...],
            // ... 引擎状态信息
        }
    """
    # 验证 API Key
    auth_key = request.headers.get('X-API-Key')
    if auth_key != API_KEY:
        return jsonify({"error": "Unauthorized", "message": "Invalid API Key"}), 401
    
    try:
        response = requests.get(
            API_STATE,
            headers=get_api_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            result = safe_json_response(response)
            return jsonify(result)
        else:
            error_result = safe_json_response(response)
            return jsonify(error_result), response.status_code
            
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Connection failed", "message": str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def api_reset():
    """API端 - 重置引擎
    
    请求头:
        X-API-Key: API认证密钥
        X-Session-ID: 会话ID（可选）
    
    响应:
        {
            "status": "ok",
            "message": "Engine reset"
        }
    """
    # 验证 API Key
    auth_key = request.headers.get('X-API-Key')
    if auth_key != API_KEY:
        return jsonify({"error": "Unauthorized", "message": "Invalid API Key"}), 401
    
    # 清除当前会话
    session_id = get_session_id()
    clear_session_data(session_id)
    
    try:
        response = requests.post(
            API_RESET,
            headers=get_api_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            result = safe_json_response(response)
            result["session_id"] = session_id
            return jsonify(result)
        else:
            error_result = safe_json_response(response)
            return jsonify(error_result), response.status_code
            
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Connection failed", "message": str(e)}), 500


@app.route('/api/session', methods=['GET'])
def api_session_info():
    """API端 - 获取会话信息
    
    请求头:
        X-API-Key: API认证密钥
        X-Session-ID: 会话ID
    
    响应:
        {
            "session_id": "会话ID",
            "engine_started": true/false,
            "npc_name": "NPC名称",
            "history_count": 对话历史数量
        }
    """
    # 验证 API Key
    auth_key = request.headers.get('X-API-Key')
    if auth_key != API_KEY:
        return jsonify({"error": "Unauthorized", "message": "Invalid API Key"}), 401
    
    session_id = get_session_id()
    session_data = get_session_data(session_id)
    
    return jsonify({
        "session_id": session_id,
        "engine_started": session_data.get("engine_started", False),
        "npc_name": session_data.get("npc_name"),
        "history_count": len(session_data.get("conversation_history", []))
    })


# 角色名验证正则（只允许字母、数字、下划线）
ROLE_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]+$')
# 系统角色列表
SYSTEM_ROLES = {'director', 'performer', 'predictor', 'observer', 'scheduler', 'perception'}


@app.route('/api/web/roles', methods=['GET'])
@lru_cache(maxsize=1)
def web_roles():
    """Web端 - 获取角色列表"""
    roles_dir = Path(__file__).parent / 'roles'
    roles = []
    
    if roles_dir.exists():
        for file in roles_dir.glob('*.md'):
            # 跳过.bak文件
            if file.suffix == '.bak':
                continue
            role_name = file.stem  # 去除.md后缀
            # 过滤掉系统角色
            if role_name not in SYSTEM_ROLES:
                roles.append(role_name)
    
    return jsonify({"roles": roles})


@app.route('/api/web/role/<role_name>', methods=['GET'])
def web_role_detail(role_name):
    """Web端 - 获取角色详情"""
    # 验证角色名（防止路径遍历）
    if not role_name or not ROLE_NAME_PATTERN.match(role_name):
        return jsonify({"error": "Invalid role name"}), 400
    
    # 过滤系统角色
    if role_name in SYSTEM_ROLES:
        return jsonify({"error": "Role not found"}), 404
    
    roles_dir = Path(__file__).parent / 'roles'
    
    # 使用 resolve() 检查路径是否在 roles_dir 内（防止路径遍历）
    try:
        role_file = (roles_dir / f"{role_name}.md").resolve()
        # 确保解析后的路径仍在 roles_dir 内
        if not role_file.exists() or not str(role_file).startswith(str(roles_dir.resolve())):
            return jsonify({"error": "Role not found"}), 404
    except Exception:
        return jsonify({"error": "Role not found"}), 404
    
    try:
        with open(role_file, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({"name": role_name, "content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============ 启动 ============

if __name__ == '__main__':
    port = int(os.environ.get('WEB_PORT', 8080))
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    
    print(f"=" * 50)
    print(f"Web App Starting")
    print(f"Cloud Engine URL: {CLOUD_ENGINE_URL}")
    print(f"Local Port: {port}")
    print(f"Debug Mode: {debug_mode}")
    print(f"=" * 50)
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
