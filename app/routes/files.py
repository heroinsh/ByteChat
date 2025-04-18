from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os
import shutil
from pathlib import Path
import uuid
from typing import Optional

from ..database import crud
from ..config import UPLOAD_DIR, ALLOWED_EXTENSIONS, MAX_FILE_SIZE
from .auth import get_current_user

router = APIRouter()

def get_file_extension(filename: str) -> str:
    return Path(filename).suffix.lower()

def is_allowed_file(filename: str, file_type: str) -> bool:
    return get_file_extension(filename) in ALLOWED_EXTENSIONS.get(file_type, [])

def get_upload_path(file_type: str) -> Path:
    path = UPLOAD_DIR / file_type
    path.mkdir(exist_ok=True)
    return path

@router.post("/upload/{file_type}")
async def upload_file(
    file_type: str,
    file: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    if not is_allowed_file(file.filename, file_type):
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {ALLOWED_EXTENSIONS.get(file_type, [])}"
        )

    # بررسی حجم فایل
    file_size = 0
    for chunk in file.file:
        file_size += len(chunk)
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE/1024/1024}MB"
            )
    await file.seek(0)

    # ایجاد نام فایل منحصر به فرد
    file_id = str(uuid.uuid4())
    file_extension = get_file_extension(file.filename)
    filename = f"{file_id}{file_extension}"
    
    # ذخیره فایل
    upload_path = get_upload_path(file_type)
    file_path = upload_path / filename
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "file_id": file_id,
        "filename": file.filename,
        "file_path": str(file_path.relative_to(UPLOAD_DIR)),
        "file_type": file_type
    }

@router.get("/files/{file_path:path}")
async def get_file(file_path: str):
    file_full_path = UPLOAD_DIR / file_path
    if not file_full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_full_path)

@router.delete("/files/{file_path:path}")
async def delete_file(
    file_path: str,
    current_user = Depends(get_current_user)
):
    file_full_path = UPLOAD_DIR / file_path
    if not file_full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # بررسی مالکیت فایل (این بخش باید با توجه به منطق برنامه پیاده‌سازی شود)
    # if not is_file_owner(file_path, current_user.id):
    #     raise HTTPException(status_code=403, detail="Not authorized to delete this file")
    
    file_full_path.unlink()
    return {"message": "File deleted successfully"} 