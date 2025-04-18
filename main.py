from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Form, HTTPException, UploadFile, File, Depends
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
import json
import os
import shutil
from typing import Dict, List, Set, Optional
from enum import Enum
import uuid
from pathlib import Path
import sqlite3
import hashlib
import base64
import re
import secrets

# تنظیمات امنیتی
SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# تنظیمات فایل
ALLOWED_EXTENSIONS = {
    'image': ['.jpg', '.jpeg', '.png', '.gif'],
    'audio': ['.mp3', '.wav', '.ogg'],
    'document': ['.pdf', '.doc', '.docx', '.txt']
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
FILE_EXPIRY_DAYS = 7

class MessageStatus(Enum):
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"

class MessageType(Enum):
    TEXT = "text"
    FILE = "file"
    IMAGE = "image"
    AUDIO = "audio"

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# اضافه کردن CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# اضافه کردن Session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="session",
    max_age=1800  # 30 minutes
)

# Create necessary directories
os.makedirs("data", exist_ok=True)
os.makedirs("uploads", exist_ok=True)
os.makedirs("uploads/files", exist_ok=True)
os.makedirs("uploads/images", exist_ok=True)
os.makedirs("uploads/audio", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('data/chat.db')
    c = conn.cursor()
    
    # Create users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  display_name TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Create messages table
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  sender_id INTEGER NOT NULL,
                  receiver_id INTEGER,
                  content TEXT NOT NULL,
                  message_type TEXT DEFAULT 'text',
                  file_info TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  status TEXT DEFAULT 'sent',
                  edited BOOLEAN DEFAULT FALSE,
                  reactions TEXT,
                  FOREIGN KEY (sender_id) REFERENCES users (id),
                  FOREIGN KEY (receiver_id) REFERENCES users (id))''')
    
    # Create blocked_users table
    c.execute('''CREATE TABLE IF NOT EXISTS blocked_users
                 (user_id INTEGER NOT NULL,
                  blocked_user_id INTEGER NOT NULL,
                  PRIMARY KEY (user_id, blocked_user_id),
                  FOREIGN KEY (user_id) REFERENCES users (id),
                  FOREIGN KEY (blocked_user_id) REFERENCES users (id))''')
    
    conn.commit()
    conn.close()

# Initialize global variables
active_connections: Dict[int, WebSocket] = {}
typing_users: Set[int] = set()
read_messages: Dict[int, Set[str]] = {}

# Initialize database
init_db()

def generate_user_id():
    conn = sqlite3.connect('data/chat.db')
    c = conn.cursor()
    c.execute('SELECT MAX(user_id) FROM users')
    max_id = c.fetchone()[0]
    conn.close()
    return (max_id or 0) + 1

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

class Message:
    def __init__(self, sender_id: int, content: str, timestamp: str, 
                 status: MessageStatus = MessageStatus.SENDING,
                 message_type: MessageType = MessageType.TEXT,
                 file_info: Optional[dict] = None,
                 message_id: Optional[str] = None,
                 reactions: Optional[dict] = None,
                 receiver_id: Optional[int] = None):
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.content = content
        self.timestamp = timestamp
        self.status = status
        self.message_type = message_type
        self.file_info = file_info
        self.id = message_id or str(uuid.uuid4())
        self.edited = False
        self.reactions = reactions or {}

    def to_dict(self):
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "content": self.content,
            "timestamp": self.timestamp,
            "status": self.status.value,
            "message_type": self.message_type.value,
            "file_info": self.file_info,
            "edited": self.edited,
            "reactions": self.reactions
        }

def save_message_to_db(message: Message):
    conn = sqlite3.connect('data/chat.db')
    c = conn.cursor()
    try:
        c.execute('''INSERT INTO messages (sender_id, receiver_id, content, message_type, file_info, status, reactions)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (message.sender_id, message.receiver_id, message.content, message.message_type.value,
                   json.dumps(message.file_info) if message.file_info else None,
                   message.status.value, json.dumps(message.reactions)))
        message_id = c.lastrowid
        conn.commit()
        return message_id
    except sqlite3.Error as e:
        print(f"Error saving message to database: {e}")
        raise
    finally:
        conn.close()

def update_message_in_db(message: Message):
    conn = sqlite3.connect('data/chat.db')
    c = conn.cursor()
    try:
        c.execute('''UPDATE messages SET content = ?, status = ?, edited = ?, reactions = ?
                     WHERE id = ?''',
                  (message.content, message.status.value, message.edited,
                   json.dumps(message.reactions), message.id))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error updating message in database: {e}")
        raise
    finally:
        conn.close()

def get_messages_from_db(sender_id: int, receiver_id: int, limit: int = 100) -> List[dict]:
    conn = sqlite3.connect('data/chat.db')
    c = conn.cursor()
    try:
        c.execute('''SELECT id, sender_id, receiver_id, content, message_type, file_info, created_at, status, edited, reactions
                     FROM messages 
                     WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)
                     ORDER BY created_at DESC LIMIT ?''', 
                     (sender_id, receiver_id, receiver_id, sender_id, limit))
        messages = []
        for row in c.fetchall():
            message = {
                "id": row[0],
                "sender_id": row[1],
                "receiver_id": row[2],
                "content": row[3],
                "message_type": row[4],
                "file_info": json.loads(row[5]) if row[5] else None,
                "created_at": row[6],
                "status": row[7],
                "edited": row[8],
                "reactions": json.loads(row[9]) if row[9] else {}
            }
            messages.append(message)
        return messages
    except sqlite3.Error as e:
        print(f"Error getting messages from database: {e}")
        raise
    finally:
        conn.close()

def get_user_by_id(user_id: int) -> Optional[dict]:
    conn = sqlite3.connect('data/chat.db')
    c = conn.cursor()
    try:
        c.execute('SELECT id, username, display_name FROM users WHERE id = ?', (user_id,))
        result = c.fetchone()
        if result:
            return {
                "id": result[0],
                "username": result[1],
                "display_name": result[2]
            }
        return None
    except sqlite3.Error as e:
        print(f"Error getting user by id: {e}")
        raise
    finally:
        conn.close()

def get_user_by_username(username: str) -> Optional[dict]:
    conn = sqlite3.connect('data/chat.db')
    c = conn.cursor()
    try:
        c.execute('SELECT id, username, password, display_name FROM users WHERE username = ?', (username,))
        result = c.fetchone()
        if result:
            return {
                "id": result[0],
                "username": result[1],
                "password": result[2],
                "display_name": result[3]
            }
        return None
    except sqlite3.Error as e:
        print(f"Error getting user by username: {e}")
        raise
    finally:
        conn.close()

def block_user(user_id: int, blocked_user_id: int):
    conn = sqlite3.connect('data/chat.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO blocked_users (user_id, blocked_user_id) VALUES (?, ?)',
                  (user_id, blocked_user_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def unblock_user(user_id: int, blocked_user_id: int):
    conn = sqlite3.connect('data/chat.db')
    c = conn.cursor()
    try:
        c.execute('DELETE FROM blocked_users WHERE user_id = ? AND blocked_user_id = ?',
                  (user_id, blocked_user_id))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error unblocking user: {e}")
        raise
    finally:
        conn.close()

def is_user_blocked(user_id: int, blocked_user_id: int) -> bool:
    conn = sqlite3.connect('data/chat.db')
    c = conn.cursor()
    try:
        c.execute('SELECT 1 FROM blocked_users WHERE user_id = ? AND blocked_user_id = ?',
                  (user_id, blocked_user_id))
        result = c.fetchone() is not None
        return result
    except sqlite3.Error as e:
        print(f"Error checking if user is blocked: {e}")
        raise
    finally:
        conn.close()

def get_blocked_users(user_id: int) -> List[int]:
    conn = sqlite3.connect('data/chat.db')
    c = conn.cursor()
    try:
        c.execute('SELECT blocked_user_id FROM blocked_users WHERE user_id = ?', (user_id,))
        blocked_users = [row[0] for row in c.fetchall()]
        return blocked_users
    except sqlite3.Error as e:
        print(f"Error getting blocked users: {e}")
        raise
    finally:
        conn.close()

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None, invite_code: Optional[str] = None):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error,
        "invite_code": invite_code
    })

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def validate_username(username: str) -> bool:
    return len(username) >= 4

def validate_password(password: str) -> bool:
    return len(password) >= 4

@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["id"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
async def register_user(request: Request, username: str = Form(...), password: str = Form(...), confirm_password: str = Form(...)):
    if not validate_username(username):
        return RedirectResponse(url="/?error=نام کاربری باید حداقل 4 کاراکتر باشد", status_code=303)
    
    if not validate_password(password):
        return RedirectResponse(url="/?error=رمز عبور باید حداقل 4 کاراکتر باشد", status_code=303)
    
    if password != confirm_password:
        return RedirectResponse(url="/?error=رمز عبور و تکرار آن مطابقت ندارند", status_code=303)
    
    conn = sqlite3.connect('data/chat.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                  (username, hash_password(password)))
        user_id = c.lastrowid
        conn.commit()
        return RedirectResponse(url=f"/chat?user_id={user_id}", status_code=303)
    except sqlite3.IntegrityError:
        return RedirectResponse(url="/?error=این نام کاربری قبلاً ثبت شده است", status_code=303)
    finally:
        conn.close()

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    user = get_user_by_username(username)
    if not user or not verify_password(password, user["password"]):
        return RedirectResponse(url="/?error=نام کاربری یا رمز عبور اشتباه است", status_code=303)
    
    # Store user_id in session
    request.session["user_id"] = user["id"]
    
    # Check if there's a pending invite
    invite_code = request.query_params.get("invite_code")
    if invite_code:
        return RedirectResponse(url=f"/chat?invite={invite_code}")
    
    return RedirectResponse(url=f"/chat", status_code=303)

@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request, user_id: Optional[int] = None, invite: Optional[int] = None):
    # Check if user is logged in
    if "user_id" not in request.session:
        return RedirectResponse(url="/login")
    
    current_user_id = request.session["user_id"]
    
    # Check if user exists
    conn = sqlite3.connect('data/chat.db')
    c = conn.cursor()
    c.execute('SELECT id, username, display_name FROM users WHERE id = ?', (current_user_id,))
    user = c.fetchone()
    conn.close()
    
    if not user:
        return RedirectResponse(url="/login")
    
    # If there's an invite parameter, check if the invited user exists
    if invite:
        conn = sqlite3.connect('data/chat.db')
        c = conn.cursor()
        c.execute('SELECT id, username, display_name FROM users WHERE id = ?', (invite,))
        invited_user = c.fetchone()
        conn.close()
        
        if not invited_user:
            return RedirectResponse(url="/invalid-invite")
        
        # Set the selected chat to the invited user
        selected_chat = {
            "id": invited_user[0],
            "username": invited_user[1],
            "display_name": invited_user[2]
        }
    else:
        selected_chat = None
    
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "user_id": current_user_id,
        "username": user[1],
        "display_name": user[2],
        "selected_chat": selected_chat
    })

@app.post("/profile/update")
async def update_profile(request: Request, user_id: int = Form(...), display_name: str = Form(...)):
    conn = sqlite3.connect('data/chat.db')
    c = conn.cursor()
    try:
        c.execute('UPDATE users SET display_name = ? WHERE id = ?', (display_name, user_id))
        conn.commit()
        return {"success": True, "message": "پروفایل با موفقیت به‌روزرسانی شد"}
    except sqlite3.Error as e:
        return {"success": False, "message": f"خطا در به‌روزرسانی پروفایل: {str(e)}"}
    finally:
        conn.close()

def get_file_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    for file_type, extensions in ALLOWED_EXTENSIONS.items():
        if ext in extensions:
            return file_type
    return 'other'

def clean_expired_files():
    conn = sqlite3.connect('data/chat.db')
    c = conn.cursor()
    try:
        # Get expired files
        c.execute('''
            SELECT file_path FROM messages 
            WHERE file_info IS NOT NULL 
            AND created_at < datetime('now', ?)
        ''', (f'-{FILE_EXPIRY_DAYS} days',))
        
        expired_files = c.fetchall()
        
        # Delete files from storage
        for file_path in expired_files:
            try:
                if os.path.exists(file_path[0]):
                    os.remove(file_path[0])
            except Exception as e:
                print(f"Error deleting file {file_path[0]}: {e}")
        
        # Update database to mark files as expired
        c.execute('''
            UPDATE messages 
            SET file_info = json_set(file_info, '$.expired', 1)
            WHERE file_info IS NOT NULL 
            AND created_at < datetime('now', ?)
        ''', (f'-{FILE_EXPIRY_DAYS} days',))
        
        conn.commit()
    except Exception as e:
        print(f"Error cleaning expired files: {e}")
    finally:
        conn.close()

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), current_user: int = Form(...)):
    if not file:
        return {"success": False, "message": "فایلی انتخاب نشده است"}
    
    try:
        # Check file size
        file_size = 0
        temp_file_path = f"temp_{file.filename}"
        with open(temp_file_path, "wb") as buffer:
            while True:
                chunk = await file.read(8192)
                if not chunk:
                    break
                file_size += len(chunk)
                if file_size > MAX_FILE_SIZE:
                    return {"success": False, "message": "حجم فایل بیش از حد مجاز است"}
                buffer.write(chunk)
            
        # Check file type
        file_extension = os.path.splitext(file.filename)[1].lower()
        file_type = get_file_type(file.filename)
        if file_type == 'other':
            return {"success": False, "message": "نوع فایل مجاز نیست"}
        
        # Create unique filename and directory structure
        file_id = str(uuid.uuid4())
        upload_dir = f"uploads/{file_type}/{datetime.now().strftime('%Y/%m/%d')}"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{file_id}{file_extension}")
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Clean expired files
        clean_expired_files()
        
        return {
            "success": True,
            "file_id": file_id,
            "filename": file.filename,
            "file_path": f"/uploads/{file_type}/{datetime.now().strftime('%Y/%m/%d')}/{file_id}{file_extension}",
            "message_type": file_type,
            "expired": False
        }
    except Exception as e:
        return {"success": False, "message": f"خطا در آپلود فایل: {str(e)}"}

@app.get("/uploads/{file_type}/{year}/{month}/{day}/{filename}")
async def serve_file(file_type: str, year: str, month: str, day: str, filename: str):
    file_path = f"uploads/{file_type}/{year}/{month}/{day}/{filename}"
    
    # Check if file exists and is not expired
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="فایل یافت نشد")
    
    # Check file expiration
    file_date = datetime(int(year), int(month), int(day))
    if datetime.now() - file_date > timedelta(days=FILE_EXPIRY_DAYS):
        raise HTTPException(status_code=410, detail="فایل منقضی شده است")
    
    return FileResponse(file_path)

@app.get("/invalid-invite")
async def invalid_invite(request: Request):
    return templates.TemplateResponse("invalid_invite.html", {"request": request})

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    try:
        # Check if user exists
        user = get_user_by_id(user_id)
        if not user:
            await websocket.close(code=4001, reason="User not found")
            return
            
        # Check if user is already connected
        if user_id in active_connections:
            try:
                await active_connections[user_id].close()
            except:
                pass
            del active_connections[user_id]
            
        await websocket.accept()
        active_connections[user_id] = websocket
        
        # Send welcome message
        welcome_msg = {
            "type": "system",
            "content": f"{user.get('display_name', user['username'])} به چت‌روم پیوست",
            "timestamp": datetime.now().strftime("%H:%M")
        }
        
        # Create a list of connections to avoid dictionary size change during iteration
        connections = list(active_connections.values())
        for connection in connections:
            try:
                await connection.send_json(welcome_msg)
            except:
                continue
                
        await broadcast_status()

        try:
            while True:
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                if message_data["type"] == "message":
                    # Handle public chat message
                    if not message_data.get("receiver_id"):
                        # Save message to database
                        conn = sqlite3.connect('data/chat.db')
                        cursor = conn.cursor()
                        cursor.execute(
                            "INSERT INTO messages (sender_id, content, message_type, status) VALUES (?, ?, ?, ?)",
                            (user_id, message_data["content"], "text", "sent")
                        )
                        message_id = cursor.lastrowid
                        conn.commit()
                        
                        # Get sender info
                        cursor.execute("SELECT username, display_name FROM users WHERE id = ?", (user_id,))
                        sender = cursor.fetchone()
                        conn.close()
                        
                        # Create message object
                        message = {
                            "type": "message",
                            "id": message_id,
                            "sender_id": user_id,
                            "username": sender[0],
                            "display_name": sender[1],
                            "content": message_data["content"],
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        # Broadcast to all connected users
                        connections = list(active_connections.values())
                        for connection in connections:
                            try:
                                await connection.send_json(message)
                            except:
                                continue
                    else:
                        # Handle private message
                        receiver_id = message_data["receiver_id"]
                        if receiver_id in active_connections:
                            # Save message to database
                            conn = sqlite3.connect('data/chat.db')
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT INTO messages (sender_id, receiver_id, content, message_type, status) VALUES (?, ?, ?, ?, ?)",
                                (user_id, receiver_id, message_data["content"], "text", "sent")
                            )
                            message_id = cursor.lastrowid
                            conn.commit()
                            
                            # Get sender info
                            cursor.execute("SELECT username, display_name FROM users WHERE id = ?", (user_id,))
                            sender = cursor.fetchone()
                            conn.close()
                            
                            # Create message object
                            message = {
                                "type": "message",
                                "id": message_id,
                                "sender_id": user_id,
                                "username": sender[0],
                                "display_name": sender[1],
                                "content": message_data["content"],
                                "timestamp": datetime.now().isoformat()
                            }
                            
                            # Send to receiver
                            try:
                                await active_connections[receiver_id].send_json(message)
                            except:
                                pass
                            
                            # Send to sender
                            try:
                                await websocket.send_json(message)
                            except:
                                pass
                
                elif message_data.get("type") == "typing":
                    typing_users.add(user_id)
                    await broadcast_typing_status()
                
                elif message_data.get("type") == "not_typing":
                    typing_users.discard(user_id)
                    await broadcast_typing_status()
                
        except WebSocketDisconnect:
            if user_id in active_connections:
                del active_connections[user_id]
            if user_id in typing_users:
                typing_users.discard(user_id)
            
            leave_msg = {
                "type": "system",
                "content": f"{user.get('display_name', user['username'])} چت‌روم را ترک کرد",
                "timestamp": datetime.now().strftime("%H:%M")
            }
            
            # Create a list of connections to avoid dictionary size change during iteration
            connections = list(active_connections.values())
            for connection in connections:
                try:
                    await connection.send_json(leave_msg)
                except:
                    continue
                    
            await broadcast_status()
            await broadcast_typing_status()
            
    except Exception as e:
        print(f"Error in websocket connection: {str(e)}")
        if user_id in active_connections:
            del active_connections[user_id]
        if user_id in typing_users:
            typing_users.discard(user_id)
        try:
            await websocket.close(code=4000, reason=str(e))
        except:
            pass

async def broadcast_message(message: dict, exclude: int = None):
    for user_id, client in active_connections.items():
        if user_id != exclude:
            try:
                await client.send_json(message)
            except:
                continue

async def broadcast_status():
    online_users = []
    for user_id in active_connections.keys():
        user = get_user_by_id(user_id)
        if user:
            online_users.append({
                "user_id": user["id"],
                "username": user.get("display_name", user["username"]),
                "online": True
            })
    
    for client in active_connections.values():
        try:
            await client.send_text(json.dumps({
                "type": "status",
                "users": online_users
            }))
        except:
            continue

async def broadcast_typing_status():
    typing_users_list = []
    for user_id in typing_users:
        user = get_user_by_id(user_id)
        if user:
            typing_users_list.append(f"{user['username']} ({user['id']})")
    
    if typing_users_list:
        typing_msg = Message(0, f"{'، '.join(typing_users_list)} در حال تایپ...", datetime.now().strftime("%H:%M"))
    else:
        typing_msg = Message(0, "", datetime.now().strftime("%H:%M"))
    
    for client in active_connections.values():
        try:
            await client.send_text(json.dumps(typing_msg.to_dict()))
        except:
            continue

async def update_message_status(message_id: str, status: MessageStatus):
    conn = sqlite3.connect('data/chat.db')
    c = conn.cursor()
    try:
        c.execute('''UPDATE messages SET status = ? WHERE id = ?''',
                  (status.value, message_id))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error updating message status: {e}")
        raise
    finally:
        conn.close()

async def edit_message(message_id: str, new_content: str, user_id: int):
    for msg in get_messages_from_db(0, 0):  # This needs to be updated to get specific messages
        if msg["id"] == message_id and msg["sender_id"] == user_id:
            msg["content"] = new_content
            msg["edited"] = True
            update_message_in_db(Message(
                msg["sender_id"],
                msg["content"],
                msg["timestamp"],
                status=MessageStatus(msg["status"]),
                message_type=MessageType(msg["message_type"]),
                file_info=msg["file_info"],
                message_id=msg["id"],
                reactions=msg["reactions"]
            ))
            await broadcast_message(msg)
            break

async def delete_message(message_id: str, user_id: int):
    for msg in get_messages_from_db(0, 0):  # This needs to be updated to get specific messages
        if msg["id"] == message_id and msg["sender_id"] == user_id:
            if msg["message_type"] != "text":
                file_path = msg["file_info"]["file_path"]
                try:
                    os.remove(file_path.lstrip("/"))
                except:
                    pass
            update_message_in_db(Message(
                msg["sender_id"],
                msg["content"],
                msg["timestamp"],
                status=MessageStatus(msg["status"]),
                message_type=MessageType(msg["message_type"]),
                file_info=msg["file_info"],
                message_id=msg["id"],
                reactions=msg["reactions"]
            ))
            await broadcast_message({
                "type": "delete",
                "message_id": message_id
            })
            break

@app.get("/invite/{invite_code}")
async def handle_invite(request: Request, invite_code: str):
    # Check if user is already logged in
    if "user_id" in request.session:
        # Redirect to private chat with the inviter
        return RedirectResponse(url=f"/chat?invite={invite_code}")
    else:
        # Store invite code in session and redirect to login
        request.session["invite_code"] = invite_code
        return RedirectResponse(url="/login")

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")
