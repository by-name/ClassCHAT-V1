// main.js - Class-Chat 完整版

let ws = null;
let heartbeatTimer = null;
let reconnectTimer = null;

// ---------- WebSocket ----------
function getWsUrl() {
    return `ws://${location.hostname}:8765`;
}

function connectWebSocket() {
    ws = new WebSocket(getWsUrl());

    ws.onopen = () => {
        clearInterval(reconnectTimer);
        reconnectTimer = null;

        heartbeatTimer = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000);

        const saved = sessionStorage.getItem('cc_account');
        const savedPw = sessionStorage.getItem('cc_password');
        if (saved && savedPw) {
            doLoginWith(saved, savedPw);
        }
    };

    ws.onmessage = (event) => {
        try {
            handleMessage(JSON.parse(event.data));
        } catch (e) {
            console.error('解析失败:', e);
        }
    };

    ws.onclose = () => {
        clearInterval(heartbeatTimer);
        if (!reconnectTimer) {
            reconnectTimer = setInterval(connectWebSocket, 3000);
        }
    };

    ws.onerror = () => ws.close();
}

function sendRaw(obj) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(obj));
    }
}

// ---------- 登录/注册切换 ----------
function toggleRegister() {
    document.getElementById('login-form').classList.toggle('hidden');
    document.getElementById('register-form').classList.toggle('hidden');
    document.getElementById('to-register').classList.toggle('hidden');
    document.getElementById('to-login').classList.toggle('hidden');
}

// ---------- 登录 ----------
function doLogin() {
    const account = document.getElementById('login-account').value.trim();
    const password = document.getElementById('login-password').value;
    if (!account || !password) {
        document.getElementById('login-error').textContent = '请输入账号和密码';
        return;
    }
    doLoginWith(account, password);
}

function doLoginWith(account, password) {
    sendRaw({ type: 'login', account_name: account, password: password });
}

function doRegister() {
    const username = document.getElementById('reg-username').value.trim();
    const account = document.getElementById('reg-account').value.trim();
    const password = document.getElementById('reg-password').value;

    if (!username || !account || !password) {
        document.getElementById('register-error').textContent = '请填写完整信息';
        return;
    }

    sendRaw({
        type: 'register',
        username: username,
        account_name: account,
        password: password
    });
}

// ---------- 聊天功能 ----------
function sendMessage() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text) return;
    sendRaw({ type: 'chat', message: text });
    input.value = '';
    input.focus();
}

function sendAnnouncement() {
    const text = document.getElementById('announce-input').value.trim();
    if (!text) return;
    sendRaw({ type: 'announcement', message: text });
    document.getElementById('announce-input').value = '';
    toggleAnnouncePanel();
}

function banAccount() {
    const target = document.getElementById('ban-input').value.trim();
    if (!target) return;
    if (confirm('确定封禁 ' + target + '？')) {
        sendRaw({ type: 'ban_account', target_account: target });
        document.getElementById('ban-input').value = '';
        toggleAdminPanel();
    }
}

function clearChatHistory() {
    if (confirm('确定清空所有聊天记录？')) {
        sendRaw({ type: 'clear_chat_history' });
        toggleAdminPanel();
    }
}

function uploadFile() {
    const file = document.getElementById('file-input').files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
        sendRaw({
            type: 'file_upload',
            filename: file.name,
            data: reader.result
        });
    };
    reader.readAsDataURL(file);
    document.getElementById('file-input').value = '';
}

// ---------- UI ----------
function toggleAnnouncePanel() {
    document.getElementById('announce-panel').classList.toggle('hidden');
}

function toggleAdminPanel() {
    document.getElementById('admin-panel').classList.toggle('hidden');
}

function doLogout() {
    sessionStorage.clear();
    if (ws) ws.close();
    location.reload();
}

// ---------- 消息处理 ----------
function handleMessage(data) {
    switch (data.type) {
        case 'login_success':
            sessionStorage.setItem('cc_account', data.account_name);
            sessionStorage.setItem('cc_password', document.getElementById('login-password').value);

            document.getElementById('login-page').classList.remove('active');
            document.getElementById('chat-page').classList.add('active');

            document.getElementById('current-user-info').textContent =
                (data.is_admin ? '👑 ' : '') + data.username;

            if (data.is_admin) {
                document.getElementById('announce-btn').classList.remove('hidden');
                document.getElementById('admin-btn').classList.remove('hidden');
            }

            // 加载历史
            data.history.forEach(msg => {
                if (msg.type === 'chat') appendChatMsg(msg);
                else if (msg.type === 'system') appendSystemMsg(msg.message);
            });
            break;

        case 'login_failed':
            document.getElementById('login-error').textContent = data.message;
            break;

        case 'register_success':
            alert(data.message);
            toggleRegister();
            break;

        case 'register_failed':
            document.getElementById('register-error').textContent = data.message;
            break;

        case 'chat':
            appendChatMsg(data);
            break;

        case 'user_list':
            updateUserList(data.users);
            break;

        case 'announcement':
            appendSystemMsg('📢 公告：' + data.message);
            break;

        case 'system':
            appendSystemMsg(data.message);
            break;

        case 'success':
            alert('✅ ' + data.message);
            break;

        case 'error':
            alert('❌ ' + data.message);
            break;
    }
}

function appendChatMsg(data) {
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = 'msg-other';
    div.innerHTML = `
        <span class="msg-user">${escHtml(data.username)}</span>
        <span class="msg-time">${data.time}</span>
        <div>${escHtml(data.message)}</div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function appendSystemMsg(text) {
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = 'msg-system';
    div.textContent = text;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function updateUserList(users) {
    const list = document.getElementById('user-list');
    document.getElementById('online-count').textContent = users.length;
    list.innerHTML = '';
    users.forEach(u => {
        const div = document.createElement('div');
        div.className = 'user-item';
        div.textContent = u.username || u.account_name;
        list.appendChild(div);
    });
}

function escHtml(text) {
    const d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
}

// ---------- 启动 ----------
connectWebSocket();