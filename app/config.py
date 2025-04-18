from pydantic import BaseSettings
from typing import Optional
import os
from pathlib import Path

class Settings(BaseSettings):
    # تنظیمات پایگاه داده
    DATABASE_URL: str = "sqlite:///data/chat.db"
    
    # تنظیمات JWT
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # تنظیمات فایل‌ها
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_FILE_TYPES: list = ["image/jpeg", "image/png", "application/pdf", "audio/mpeg"]
    
    # تنظیمات WebSocket
    WS_PING_INTERVAL: int = 20
    WS_PING_TIMEOUT: int = 20
    WS_CLOSE_TIMEOUT: int = 5
    
    # تنظیمات سرور
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"

# ایجاد مسیرهای مورد نیاز
def create_directories():
    Path("data").mkdir(exist_ok=True)
    Path("uploads").mkdir(exist_ok=True)
    Path("uploads/files").mkdir(exist_ok=True)
    Path("uploads/images").mkdir(exist_ok=True)
    Path("uploads/audio").mkdir(exist_ok=True)

settings = Settings()
create_directories() 