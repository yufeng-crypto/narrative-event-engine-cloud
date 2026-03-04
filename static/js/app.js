// Narrative Engine Web - Client Script

// API 配置
const API_BASE_PATH = '/api/web';

class NarrativeEngineClient {
    constructor() {
        this.apiBase = API_BASE_PATH;
        this.engineStarted = false;
        this.currentRole = '';
        this.conversationHistory = [];
        
        // 六轴默认值
        this.axes = {
            Intimacy: 0,
            Risk: 0,
            Info: 0,
            Action: 0,
            Rel: 0,
            Growth: 0
        };
        
        // 当前事件卡
        this.currentEvent = null;
        
        this.initElements();
        this.bindEvents();
        this.loadCsrfToken();
        this.loadRoles();
    }
    
    // 获取 CSRF Token
    async loadCsrfToken() {
        try {
            // 从 meta 标签获取 CSRF token
            const csrfMeta = document.querySelector('meta[name="csrf-token"]');
            if (csrfMeta) {
                this.csrfToken = csrfMeta.getAttribute('content');
            }
        } catch (error) {
            console.error('Failed to load CSRF token:', error);
        }
    }
    
    // 带 CSRF 和超时的 fetch 辅助方法
    async fetchWithTimeout(url, options = {}, timeout = 30000) {
        const controller = new AbortController();
        const id = setTimeout(() => controller.abort(), timeout);
        
        // 添加 CSRF token 到请求头
        const headers = {
            ...options.headers,
            'X-CSRF-Token': this.csrfToken
        };
        
        try {
            const response = await fetch(url, {
                ...options,
                headers,
                signal: controller.signal,
                credentials: 'include'
            });
            clearTimeout(id);
            return response;
        } catch (error) {
            clearTimeout(id);
            if (error.name === 'AbortError') {
                throw new Error('请求超时，请稍后重试');
            }
            throw error;
        }
    }
    
    initElements() {
        // Toolbar
        this.roleSelect = document.getElementById('role-select');
        this.sendBtn = document.getElementById('send-btn');
        this.saveBtn = document.getElementById('save-btn');
        this.newChatBtn = document.getElementById('new-chat-btn');
        
        // Chat
        this.chatHistory = document.getElementById('chat-history');
        this.userInput = document.getElementById('user-input');
        
        // Status
        this.axesDisplay = document.getElementById('axes-display');
        this.eventCard = document.getElementById('event-card');
        
        // Engine status
        this.engineStatus = document.getElementById('engine-status');
        
        // Loading indicator
        this.loadingIndicator = document.getElementById('loading-indicator');
        
        // Debug section
        this.debugTabs = document.querySelectorAll('.debug-tab');
        this.debugInput = document.getElementById('debug-input');
        this.debugOutput = document.getElementById('debug-output');
        this.currentDebugTab = 'perception';
        
        // 保存各模块的调试信息
        this.debugInfo = {
            perception: { input: '', output: '' },
            director: { input: '', output: '' },
            predictor: { input: '', output: '' },
            performer: { input: '', output: '' }
        };
    }
    
    bindEvents() {
        // 角色选择
        this.roleSelect?.addEventListener('change', (e) => this.handleRoleChange(e));
        
        // 发送按钮
        this.sendBtn?.addEventListener('click', () => this.handleSend());
        
        // 保存按钮
        this.saveBtn?.addEventListener('click', () => this.handleSave());
        
        // 新对话按钮
        this.newChatBtn?.addEventListener('click', () => this.handleNewChat());
        
        // 输入框 - Enter发送, Shift+Enter换行
        this.userInput?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.handleSend();
            }
        });
        
        // 调试标签页切换
        this.debugTabs?.forEach(tab => {
            tab.addEventListener('click', (e) => this.handleDebugTabClick(e));
        });
    }
    
    // 加载角色列表
    async loadRoles() {
        try {
            const response = await this.fetchWithTimeout(`${this.apiBase}/roles`, {}, 5000);
            const result = await response.json();
            
            if (response.ok && result.roles) {
                this.populateRoleSelect(result.roles);
            }
        } catch (error) {
            console.error('Load roles error:', error);
        }
    }
    
    populateRoleSelect(roles) {
        if (!this.roleSelect) return;
        
        // 保留第一个默认选项
        this.roleSelect.innerHTML = '<option value="">-- 选择角色 --</option>';
        
        roles.forEach(role => {
            const option = document.createElement('option');
            option.value = role;
            // 处理角色名称（npc_xxx -> xxx 或者直接显示）
            option.textContent = role ? role.replace(/^npc_/, '') : role;
            this.roleSelect.appendChild(option);
        });
    }
    
    // 角色选择变更
    async handleRoleChange(e) {
        if (!e.target) return;
        const roleName = e.target.value;
        
        if (!roleName) {
            this.resetUI();
            return;
        }
        
        this.currentRole = roleName;
        
        // 启用输入
        this.enableChat(true);
        
        // 初始化引擎
        await this.initEngine(roleName);
    }
    
    // 初始化引擎
    async initEngine(roleName) {
        try {
            const response = await this.fetchWithTimeout(`${this.apiBase}/start`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    npc_name: roleName,
                    profile: null
                })
            }, 30000);
            
            const result = await response.json();
            
            if (response.ok) {
                this.engineStarted = true;
                
                // 清空对话历史
                this.conversationHistory = [];
                this.updateChatDisplay();
                
                // 添加欢迎消息
                this.addMessage('npc', result.message || `已与 ${roleName} 建立对话`);
                
                // 更新状态
                this.updateEngineStatus(true);
                
                // 获取初始状态
                this.refreshState();
            } else {
                alert(result.message || '初始化失败');
                this.enableChat(false);
            }
        } catch (error) {
            console.error('Init error:', error);
            alert('连接失败: ' + error.message);
            this.enableChat(false);
        }
    }
    
    // 发送消息
    async handleSend() {
        const message = this.userInput.value.trim();
        if (!message || !this.engineStarted) return;
        
        // 保存最后发送的消息（用于轮询恢复）
        this.lastUserMessage = message;
        
        // 显示加载状态
        this.showLoading();
        
        // 禁用输入
        this.userInput.disabled = true;
        this.sendBtn.disabled = true;
        
        // 添加用户消息
        this.addMessage('user', message);
        this.userInput.value = '';
        
        // 添加到历史记录
        this.conversationHistory.push({ role: 'user', content: message });
        
        try {
            const response = await this.fetchWithTimeout(`${this.apiBase}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: message,
                    history: this.conversationHistory
                })
            }, 60000);
            
            const result = await response.json();
            
            // 隐藏加载状态
            this.hideLoading();
            
            if (response.ok) {
                // 添加NPC回复
                const npcMessage = result.npc || result.response || '（无回复）';
                this.addMessage('npc', npcMessage);
                
                // 添加到历史记录
                this.conversationHistory.push({ role: 'npc', content: npcMessage });
                
                // 更新六轴状态
                if (result.axes) {
                    this.updateAxes(result.axes);
                }
                
                // 更新事件卡 - 传递原始 predictor 输出
                if (result.predictor_raw_output) {
                    this.updateEventCard({ _raw_output: result.predictor_raw_output });
                } else if (result.event) {
                    this.updateEventCard(result.event);
                }
                
                // 更新调试信息
                this.updateDebugInfo(result);
                
                // 检查是否需要轮询（如果后端返回 pending 状态）
                if (result.pending) {
                    this.startPolling(message, this.conversationHistory);
                    return; // 提前返回，不启用输入
                }
            } else {
                this.addMessage('npc', `错误: ${result.message}`);
            }
        } catch (error) {
            console.error('Chat error:', error);
            this.hideLoading();
            this.addMessage('npc', `连接失败: ${error.message}`);
        } finally {
            // 只有不在轮询时才启用输入
            if (!this.pollInterval) {
                this.userInput.disabled = false;
                this.sendBtn.disabled = false;
                this.userInput.focus();
            }
        }
    }
    
    // 保存对话
    handleSave() {
        if (this.conversationHistory.length === 0) {
            alert('没有对话内容可保存');
            return;
        }
        
        const data = {
            role: this.currentRole,
            timestamp: new Date().toISOString(),
            axes: this.axes,
            event: this.currentEvent,
            history: this.conversationHistory
        };
        
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `dialogue_${this.currentRole}_${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }
    
    // 新对话
    handleNewChat() {
        if (this.conversationHistory.length > 0) {
            if (!confirm('确定要开始新对话吗？当前对话将被清除。')) {
                return;
            }
        }
        
        // 重置对话
        this.conversationHistory = [];
        this.updateChatDisplay();
        
        // 重置六轴
        this.updateAxes({
            Intimacy: 0,
            Risk: 0,
            Info: 0,
            Action: 0,
            Rel: 0,
            Growth: 0
        });
        
        // 清空事件卡
        this.updateEventCard(null);
        
        // 重置调试信息
        this.resetDebugInfo();
        
        // 重新初始化引擎
        if (this.currentRole) {
            this.initEngine(this.currentRole);
        }
    }
    
    // 刷新状态
    async refreshState() {
        try {
            const response = await this.fetchWithTimeout(`${this.apiBase}/state`, {}, 5000);
            const result = await response.json();
            
            if (response.ok) {
                if (result.axes) {
                    this.updateAxes(result.axes);
                }
                if (result.event) {
                    this.updateEventCard(result.event);
                }
            }
        } catch (error) {
            console.error('Refresh state error:', error);
        }
    }
    
    // 添加消息到显示区域
    addMessage(sender, content) {
        // 移除空状态提示
        const emptyState = this.chatHistory.querySelector('.empty-state');
        if (emptyState) {
            emptyState.remove();
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        
        const label = document.createElement('div');
        label.className = 'message-label';
        label.textContent = sender === 'user' ? '你' : this.currentRole || 'NPC';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = content;
        
        messageDiv.appendChild(label);
        messageDiv.appendChild(contentDiv);
        
        this.chatHistory.appendChild(messageDiv);
        
        // 滚动到底部
        this.chatHistory.scrollTop = this.chatHistory.scrollHeight;
    }
    
    // 更新对话显示
    updateChatDisplay() {
        if (this.conversationHistory.length === 0) {
            this.chatHistory.innerHTML = '<div class="empty-state"><p>请选择一个角色开始对话</p></div>';
        } else {
            this.chatHistory.innerHTML = '';
            this.conversationHistory.forEach(msg => {
                this.addMessage(msg.role, msg.content);
            });
        }
    }
    
    // 更新六轴显示
    updateAxes(axes) {
        if (!axes) return;
        
        // 更新内存中的值
        this.axes = { ...this.axes, ...axes };
        
        // 更新UI
        const maxValue = 10; // 假设最大值为10
        
        Object.keys(this.axes).forEach(axisName => {
            const value = Number(this.axes[axisName]);
            const percent = Math.min((value / maxValue) * 100, 100);
            
            // 查找对应的元素
            const axisItem = this.axesDisplay?.querySelector(`[data-axis="${axisName}"]`);
            if (axisItem) {
                const fill = axisItem.parentElement?.querySelector('.axis-fill');
                if (fill) {
                    fill.style.width = `${percent}%`;
                    
                    // 根据值设置颜色
                    fill.classList.remove('warning', 'danger');
                    if (value >= 8) {
                        fill.classList.add('danger');
                    } else if (value >= 6) {
                        fill.classList.add('warning');
                    }
                }
                axisItem.textContent = value;
            }
        });
    }
    
    // 更新事件卡显示
    updateEventCard(event) {
        this.currentEvent = event;
        
        if (!event) {
            this.eventCard.innerHTML = '<div class="event-empty"><p>暂无事件</p></div>';
            return;
        }
        
        // 直接显示原始事件数据（JSON格式）
        this.eventCard.innerHTML = '';
        const content = document.createElement('div');
        content.className = 'event-content';

        // 如果有原始 raw_output，直接显示
        if (event._raw_output) {
            const pre = document.createElement('pre');
            pre.style.whiteSpace = 'pre-wrap';
            pre.style.wordBreak = 'break-all';
            pre.style.fontSize = '12px';
            pre.style.margin = '0';
            pre.textContent = event._raw_output;
            content.appendChild(pre);
        } else {
            // 兼容旧格式：解析显示
            const title = document.createElement('div');
            title.className = 'event-title';
            title.textContent = event.title || event.event_id || '未知事件';

            const archetype = document.createElement('div');
            archetype.className = 'event-archetype';
            archetype.textContent = `类型: ${event.archetype || event.archetype_ref || '未知'}`;

            const hook = document.createElement('div');
            hook.className = 'event-hook';
            hook.textContent = event.plot_hook || event.trigger || '';

            content.appendChild(title);
            content.appendChild(archetype);
            content.appendChild(hook);
        }

        this.eventCard.appendChild(content);
    }
    
    // 启用/禁用聊天
    enableChat(enabled) {
        this.userInput.disabled = !enabled;
        this.sendBtn.disabled = !enabled;
        this.saveBtn.disabled = !enabled;
    }
    
    // 显示加载状态
    showLoading() {
        if (this.loadingIndicator) {
            this.loadingIndicator.style.display = 'flex';
        }
        // 添加等待消息
        this.isWaitingForResponse = true;
        this.addMessage('npc', '正在思考...');
        this.waitingMessage = this.chatHistory.lastElementChild;
    }
    
    // 隐藏加载状态
    hideLoading() {
        if (this.loadingIndicator) {
            this.loadingIndicator.style.display = 'none';
        }
        // 移除等待消息
        if (this.waitingMessage && this.waitingMessage.querySelector('.message-content')?.textContent === '正在思考...') {
            this.waitingMessage.remove();
            this.waitingMessage = null;
        }
        this.isWaitingForResponse = false;
    }
    
    // 轮询获取对话结果（备用方案，用于长响应场景）
    startPolling(message, history) {
        this.stopPolling();
        this.pollInterval = setInterval(async () => {
            try {
                const response = await this.fetchWithTimeout(`${this.apiBase}/state`, {}, 5000);
                const result = await response.json();
                
                if (response.ok && result.pending_response) {
                    // 有待处理的响应
                    this.handlePollingResponse(result);
                }
            } catch (error) {
                console.error('Polling error:', error);
            }
        }, 2000); // 每2秒轮询一次
    }
    
    // 停止轮询
    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    }
    
    // 处理轮询响应
    handlePollingResponse(result) {
        if (result.npc) {
            // 移除等待消息
            this.hideLoading();
            this.stopPolling();
            
            // 添加NPC回复
            this.addMessage('npc', result.npc);
            this.conversationHistory.push({ role: 'user', content: this.lastUserMessage });
            this.conversationHistory.push({ role: 'npc', content: result.npc });
            
            // 更新六轴
            if (result.axes) {
                this.updateAxes(result.axes);
            }
            
            // 更新事件卡
            if (result.event) {
                this.updateEventCard(result.event);
            }
            
            // 启用输入
            this.userInput.disabled = false;
            this.sendBtn.disabled = false;
            this.userInput.focus();
        }
    }
    
    // 重置UI
    resetUI() {
        this.engineStarted = false;
        this.currentRole = '';
        this.conversationHistory = [];
        this.updateChatDisplay();
        this.enableChat(false);
        
        // 重置六轴
        this.updateAxes({
            Intimacy: 0,
            Risk: 0,
            Info: 0,
            Action: 0,
            Rel: 0,
            Growth: 0
        });
        
        // 清空事件卡
        this.updateEventCard(null);
        
        this.updateEngineStatus(false);
    }
    
    // 更新引擎状态显示
    updateEngineStatus(online) {
        if (this.engineStatus) {
            const dot = this.engineStatus.querySelector('.status-dot');
            if (dot) {
                dot.className = online ? 'status-dot online' : 'status-dot offline';
            }
            this.engineStatus.innerHTML = online 
                ? '<span class="status-dot online"></span> 云端引擎: 已连接'
                : '<span class="status-dot offline"></span> 云端引擎: 未连接';
        }
    }
    
    // 更新调试信息
    updateDebugInfo(result) {
        if (!result) return;
        
        // Perception
        this.debugInfo.perception = {
            input: result.perception_input || '',
            output: result.perception_raw_output || JSON.stringify(result.perception_output, null, 2) || ''
        };
        
        // Director
        this.debugInfo.director = {
            input: result.director_input || '',
            output: result.director_raw_output || JSON.stringify(result.director_output, null, 2) || ''
        };
        
        // Predictor
        this.debugInfo.predictor = {
            input: result.predictor_input || '',
            output: result.predictor_raw_output || JSON.stringify(result.predictor_output, null, 2) || ''
        };
        
        // Performer
        this.debugInfo.performer = {
            input: result.performer_input || '',
            output: result.performer_raw_output || result.performer_output || ''
        };
        
        // 更新当前标签页的显示
        this.updateDebugDisplay();
    }
    
    // 调试标签页点击处理
    handleDebugTabClick(e) {
        const tab = e.target;
        const tabName = tab.dataset.tab;
        
        // 更新激活状态
        this.debugTabs?.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        
        // 更新当前标签
        this.currentDebugTab = tabName;
        
        // 更新显示
        this.updateDebugDisplay();
    }
    
    // 更新调试显示
    updateDebugDisplay() {
        if (!this.debugInput || !this.debugOutput) return;
        
        const info = this.debugInfo[this.currentDebugTab];
        if (info) {
            this.debugInput.textContent = info.input || '（无数据）';
            this.debugOutput.textContent = info.output || '（无数据）';
        }
    }
    
    // 重置调试信息
    resetDebugInfo() {
        this.debugInfo = {
            perception: { input: '', output: '' },
            director: { input: '', output: '' },
            predictor: { input: '', output: '' },
            performer: { input: '', output: '' }
        };
        this.debugInput.textContent = '等待对话开始...';
        this.debugOutput.textContent = '等待对话开始...';
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.engineClient = new NarrativeEngineClient();
});
