from sqlalchemy.orm import Session
from . import models
from datetime import datetime
import uuid

# User operations
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, username: str, password: str):
    db_user = models.User(username=username, password=password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_status(db: Session, user_id: int, is_online: bool):
    user = get_user(db, user_id)
    if user:
        user.is_online = is_online
        user.last_seen = datetime.utcnow()
        db.commit()
        return user
    return None

# Message operations
def create_message(db: Session, sender_id: int, content: str, message_type: str = "text", file_info: dict = None):
    message_id = str(uuid.uuid4())
    db_message = models.Message(
        id=message_id,
        sender_id=sender_id,
        content=content,
        message_type=message_type,
        file_info=file_info,
        status="sending"
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message

def get_message(db: Session, message_id: str):
    return db.query(models.Message).filter(models.Message.id == message_id).first()

def update_message_status(db: Session, message_id: str, status: str):
    message = get_message(db, message_id)
    if message:
        message.status = status
        db.commit()
        return message
    return None

def edit_message(db: Session, message_id: str, new_content: str):
    message = get_message(db, message_id)
    if message:
        message.content = new_content
        message.edited = True
        db.commit()
        return message
    return None

def get_messages(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Message).offset(skip).limit(limit).all()

# Reaction operations
def add_reaction(db: Session, message_id: str, user_id: int, reaction: str):
    db_reaction = models.Reaction(
        message_id=message_id,
        user_id=user_id,
        reaction=reaction
    )
    db.add(db_reaction)
    db.commit()
    db.refresh(db_reaction)
    return db_reaction

def get_message_reactions(db: Session, message_id: str):
    return db.query(models.Reaction).filter(models.Reaction.message_id == message_id).all() 