from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path

from .config import DATABASE_URL, UPLOAD_DIR
from .database import models
from .routes import auth, chat, files

# ایجاد موتور پایگاه داده
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ایجاد جداول پایگاه داده
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Chat Room API")

# تنظیمات CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# اتصال مسیرهای استاتیک
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# اتصال مسیرهای API
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(files.router, prefix="/api/files", tags=["files"])

@app.get("/")
async def root():
    return {"message": "Welcome to Chat Room API"} 