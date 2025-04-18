from fastapi import WebSocket, WebSocketDisconnect
from .connection_manager import ConnectionManager
from ..database import crud
from sqlalchemy.orm import Session
from datetime import datetime
import json

class WebSocketHandler:
    def __init__(self, manager: ConnectionManager, db: Session):
        self.manager = manager
        self.db = db

    async def handle_connection(self, websocket: WebSocket, username: str):
        await self.manager.connect(websocket, username)
        try:
            # ارسال پیام خوش‌آمدگویی
            await self.manager.send_personal_message({
                "type": "system",
                "content": f"خوش آمدید {username}!"
            }, username)

            # بروزرسانی لیست کاربران برای همه
            await self.manager.broadcast_user_list()

            # ارسال پیام ورود به چت
            await self.manager.broadcast({
                "type": "user_joined",
                "username": username
            }, exclude=username)

            while True:
                data = await websocket.receive_text()
                message_data = json.loads(data)

                if message_data["type"] == "typing":
                    self.manager.add_typing_user(username)
                    await self.manager.broadcast_typing_status()
                    continue

                if message_data["type"] == "not_typing":
                    self.manager.remove_typing_user(username)
                    await self.manager.broadcast_typing_status()
                    continue

                if message_data["type"] == "message":
                    # ذخیره پیام در پایگاه داده
                    message = crud.create_message(
                        self.db,
                        sender_id=message_data["sender_id"],
                        content=message_data["content"],
                        message_type=message_data.get("message_type", "text"),
                        file_info=message_data.get("file_info")
                    )

                    # ارسال پیام به همه کاربران
                    await self.manager.broadcast({
                        "type": "message",
                        "id": message.id,
                        "sender": username,
                        "content": message.content,
                        "message_type": message.message_type,
                        "file_info": message.file_info,
                        "timestamp": message.timestamp.isoformat(),
                        "status": message.status
                    })

                elif message_data["type"] == "reaction":
                    # ذخیره واکنش در پایگاه داده
                    reaction = crud.add_reaction(
                        self.db,
                        message_id=message_data["message_id"],
                        user_id=message_data["user_id"],
                        reaction=message_data["reaction"]
                    )

                    # ارسال واکنش به همه کاربران
                    await self.manager.broadcast({
                        "type": "reaction",
                        "message_id": message_data["message_id"],
                        "user_id": message_data["user_id"],
                        "username": username,
                        "reaction": message_data["reaction"]
                    })

        except WebSocketDisconnect:
            self.manager.disconnect(username)
            await self.manager.broadcast({
                "type": "user_left",
                "username": username
            })
            await self.manager.broadcast_user_list() 