from typing import Dict, Set
from fastapi import WebSocket
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.typing_users: Set[str] = set()

    async def connect(self, websocket: WebSocket, username: str):
        await websocket.accept()
        self.active_connections[username] = websocket

    def disconnect(self, username: str):
        if username in self.active_connections:
            del self.active_connections[username]
        self.typing_users.discard(username)

    async def send_personal_message(self, message: dict, username: str):
        if username in self.active_connections:
            await self.active_connections[username].send_text(json.dumps(message))

    async def broadcast(self, message: dict, exclude: str = None):
        for username, connection in self.active_connections.items():
            if username != exclude:
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    self.disconnect(username)

    async def broadcast_user_list(self):
        user_list = [{"username": username, "online": True} 
                    for username in self.active_connections.keys()]
        await self.broadcast({"type": "user_list", "users": user_list})

    def add_typing_user(self, username: str):
        self.typing_users.add(username)

    def remove_typing_user(self, username: str):
        self.typing_users.discard(username)

    async def broadcast_typing_status(self):
        if self.typing_users:
            typing_message = {
                "type": "typing",
                "usernames": list(self.typing_users)
            }
            await self.broadcast(typing_message)
        else:
            await self.broadcast({"type": "typing", "usernames": []}) 