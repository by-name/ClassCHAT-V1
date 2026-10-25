# chat_websocket.py
import asyncio
import websockets
import json
import os
import base64
from datetime import datetime

# ========== 配置 ==========
HOST = "0.0.0.0"
PORT = 8765
ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "Account.json")
FILE_DIR = os.path.join(os.path.dirname(__file__), "file")

# ========== 全局状态 ==========
CLIENTS = {}
BANNED = set()
CHAT_HISTORY = []
MAX_HISTORY = 500

# ========== 工具函数 ==========
def load_accounts():
    try:
        with open(ACCOUNT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] 加载 Account.json 失败: {e}")
        return []

def save_accounts(accounts):
    try:
        with open(ACCOUNT_FILE, "w", encoding="utf-8") as f:
            json.dump(accounts, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[ERROR] 保存 Account.json 失败: {e}")
        return False

def parse_privileges(priv_str):
    if not priv_str or priv_str == "empty":
        return []
    return [p.strip() for p in priv_str.split(",")]

def get_account(account_name, password):
    accounts = load_accounts()
    for acc in accounts:
        if acc.get("account_name") == account_name and acc.get("password") == password:
            return acc
    return None

def get_online_users():
    return [
        {
            "account_name": info["account_name"],
            "username": info["username"]
        }
        for info in CLIENTS.values()
    ]

# ========== 广播 ==========
async def broadcast(message: dict):
    if not CLIENTS:
        return
    payload = json.dumps(message, ensure_ascii=False)
    await asyncio.wait([ws.send(payload) for ws in CLIENTS.keys()])

async def send_to(ws, message: dict):
    try:
        await ws.send(json.dumps(message, ensure_ascii=False))
    except:
        pass

# ========== 消息处理 ==========
async def handle_message(ws, raw_data):
    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError:
        await send_to(ws, {"type": "error", "message": "无效的JSON格式"})
        return

    msg_type = data.get("type")

    # ---------- 注册 ----------
    if msg_type == "register":
        new_account = data.get("account_name", "").strip()
        new_password = data.get("password", "").strip()
        new_username = data.get("username", "").strip()

        if not new_account or not new_password or not new_username:
            await send_to(ws, {"type": "register_failed", "message": "请填写完整信息"})
            return

        if len(new_account) < 3 or len(new_account) > 20:
            await send_to(ws, {"type": "register_failed", "message": "账号名长度需在3-20之间"})
            return

        if len(new_password) < 3:
            await send_to(ws, {"type": "register_failed", "message": "密码长度至少3位"})
            return

        accounts = load_accounts()

        for acc in accounts:
            if acc.get("account_name") == new_account:
                await send_to(ws, {"type": "register_failed", "message": "账号名已存在"})
                return
            if acc.get("username") == new_username:
                await send_to(ws, {"type": "register_failed", "message": "昵称已被使用"})
                return

        accounts.append({
            "username": new_username,
            "password": new_password,
            "account_name": new_account,
            "special_privileges": "empty"
        })

        if save_accounts(accounts):
            await send_to(ws, {"type": "register_success", "message": "注册成功，请登录"})
            print(f"[REGISTER] 新用户: {new_username} ({new_account})")
        else:
            await send_to(ws, {"type": "register_failed", "message": "服务器保存失败"})

    # ---------- 登录 ----------
    elif msg_type == "login":
        account_name = data.get("account_name", "").strip()
        password = data.get("password", "").strip()

        if account_name in BANNED:
            await send_to(ws, {"type": "login_failed", "message": "该账号已被封禁"})
            return

        acc = get_account(account_name, password)
        if not acc:
            await send_to(ws, {"type": "login_failed", "message": "账号或密码错误"})
            return

        # 踢掉旧登录
        for old_ws, info in list(CLIENTS.items()):
            if info["account_name"] == account_name:
                await send_to(old_ws, {"type": "kicked", "message": "账号在其他地方登录"})
                del CLIENTS[old_ws]

        privileges = parse_privileges(acc.get("special_privileges", "empty"))
        CLIENTS[ws] = {
            "account_name": acc["account_name"],
            "username": acc["username"],
            "privileges": privileges
        }

        await send_to(ws, {
            "type": "login_success",
            "username": acc["username"],
            "account_name": acc["account_name"],
            "privileges": privileges,
            "is_admin": "Account ban" in privileges,
            "history": CHAT_HISTORY[-50:]
        })

        await broadcast({
            "type": "system",
            "message": f"{acc['username']} 加入了聊天室"
        })
        await broadcast({
            "type": "user_list",
            "users": get_online_users()
        })
        print(f"[LOGIN] {acc['username']} ({account_name})")

    # ---------- 聊天 ----------
    elif msg_type == "chat":
        if ws not in CLIENTS:
            return

        user_info = CLIENTS[ws]
        content = data.get("message", "").strip()
        if not content:
            return

        msg_obj = {
            "type": "chat",
            "account_name": user_info["account_name"],
            "username": user_info["username"],
            "message": content,
            "time": datetime.now().strftime("%H:%M:%S")
        }

        CHAT_HISTORY.append(msg_obj)
        if len(CHAT_HISTORY) > MAX_HISTORY:
            CHAT_HISTORY.pop(0)

        await broadcast(msg_obj)

    # ---------- 公告 ----------
    elif msg_type == "announcement":
        if ws not in CLIENTS:
            return
        user_info = CLIENTS[ws]
        if "make_an_announcement" not in user_info["privileges"]:
            await send_to(ws, {"type": "error", "message": "无权限发布公告"})
            return

        content = data.get("message", "").strip()
        await broadcast({
            "type": "announcement",
            "message": content,
            "from": user_info["username"],
            "time": datetime.now().strftime("%H:%M:%S")
        })

    # ---------- 封禁 ----------
    elif msg_type == "ban_account":
        if ws not in CLIENTS:
            return
        user_info = CLIENTS[ws]
        if "Account ban" not in user_info["privileges"]:
            await send_to(ws, {"type": "error", "message": "无权限封禁账号"})
            return

        target = data.get("target_account", "").strip()
        if target in BANNED:
            await send_to(ws, {"type": "error", "message": "该账号已被封禁"})
            return

        BANNED.add(target)
        for client_ws, info in list(CLIENTS.items()):
            if info["account_name"] == target:
                await send_to(client_ws, {"type": "kicked", "message": "你已被管理员封禁"})
                del CLIENTS[client_ws]

        await send_to(ws, {"type": "success", "message": f"已封禁账号: {target}"})
        await broadcast({
            "type": "system",
            "message": f"账号 {target} 已被管理员封禁"
        })

    # ---------- 清空聊天记录 ----------
    elif msg_type == "clear_chat_history":
        if ws not in CLIENTS:
            return
        user_info = CLIENTS[ws]
        if "delete_chat_history" not in user_info["privileges"]:
            await send_to(ws, {"type": "error", "message": "无权限清空聊天记录"})
            return

        CHAT_HISTORY.clear()
        await broadcast({
            "type": "system",
            "message": "聊天记录已被管理员清空"
        })

    # ---------- 文件上传 ----------
    elif msg_type == "file_upload":
        if ws not in CLIENTS:
            return

        filename = data.get("filename", "unknown")
        file_data = data.get("data") or data.get("filedata")

        os.makedirs(FILE_DIR, exist_ok=True)
        filepath = os.path.join(FILE_DIR, filename)
        try:
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(file_data))
            await send_to(ws, {"type": "success", "message": f"文件 {filename} 上传成功"})
        except Exception as e:
            await send_to(ws, {"type": "error", "message": f"文件保存失败: {e}"})

    # ---------- 心跳 ----------
    elif msg_type == "ping":
        await send_to(ws, {"type": "pong"})

    else:
        await send_to(ws, {"type": "error", "message": f"未知消息类型: {msg_type}"})

# ========== WebSocket ==========
async def chat_handler(websocket):
    try:
        async for message in websocket:
            await handle_message(websocket, message)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if websocket in CLIENTS:
            user_info = CLIENTS.pop(websocket)
            await broadcast({
                "type": "system",
                "message": f"{user_info['username']} 离开了聊天室"
            })
            await broadcast({
                "type": "user_list",
                "users": get_online_users()
            })
            print(f"[LOGOUT] {user_info['username']}")

# ========== 启动 ==========
async def main():
    os.makedirs(FILE_DIR, exist_ok=True)
    async with websockets.serve(chat_handler, HOST, PORT):
        print(f"""
╔══════════════════════════════════════╗
║     Class-Chat WebSocket Server      ║
║     Listening on ws://{HOST}:{PORT}        ║
║     Press Ctrl+C to stop             ║
╚══════════════════════════════════════╝
""")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())