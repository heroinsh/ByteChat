from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    is_online = Column(Boolean, default=False)
    last_seen = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    messages = relationship("Message", back_populates="sender")
    reactions = relationship("Reaction", back_populates="user")

class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"))
    content = Column(String)
    message_type = Column(String)  # text, file, image, audio
    file_info = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String)  # sending, sent, delivered, read, failed
    edited = Column(Boolean, default=False)

    sender = relationship("User", back_populates="messages")
    reactions = relationship("Reaction", back_populates="message")

class Reaction(Base):
    __tablename__ = "reactions"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String, ForeignKey("messages.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    reaction = Column(String)  # emoji
    timestamp = Column(DateTime, default=datetime.utcnow)

    message = relationship("Message", back_populates="reactions")
    user = relationship("User", back_populates="reactions") 