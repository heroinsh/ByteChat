from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from ..database import crud, models
from ..websocket.connection_manager import ConnectionManager
from ..websocket.handlers import WebSocketHandler
from .auth import get_current_user

router = APIRouter()
manager = ConnectionManager()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/messages/", response_model=List[models.Message])
async def get_messages(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    messages = crud.get_messages(db, skip=skip, limit=limit)
    return messages

@router.post("/messages/")
async def create_message(
    content: str,
    message_type: str = "text",
    file_info: dict = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    message = crud.create_message(
        db,
        sender_id=current_user.id,
        content=content,
        message_type=message_type,
        file_info=file_info
    )
    return message

@router.put("/messages/{message_id}")
async def edit_message(
    message_id: str,
    new_content: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    message = crud.edit_message(db, message_id, new_content)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    if message.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to edit this message")
    return message

@router.post("/messages/{message_id}/reactions")
async def add_reaction(
    message_id: str,
    reaction: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    reaction = crud.add_reaction(
        db,
        message_id=message_id,
        user_id=current_user.id,
        reaction=reaction
    )
    return reaction

@router.websocket("/ws/{username}")
async def websocket_endpoint(
    websocket: WebSocket,
    username: str,
    db: Session = Depends(get_db)
):
    handler = WebSocketHandler(manager, db)
    await handler.handle_connection(websocket, username) 