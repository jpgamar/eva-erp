import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_db
from src.documents.models import Document, Folder
from src.documents.schemas import DocumentResponse, FolderCreate, FolderResponse

router = APIRouter(prefix="/documents", tags=["documents"])


# ─── Folders ──────────────────────────────────────────────────────

@router.get("/folders", response_model=list[FolderResponse])
async def list_folders(
    parent_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Folder).order_by(Folder.position)
    if parent_id:
        q = q.where(Folder.parent_id == parent_id)
    else:
        q = q.where(Folder.parent_id.is_(None))
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/folders", response_model=FolderResponse, status_code=201)
async def create_folder(
    data: FolderCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    folder = Folder(name=data.name, parent_id=data.parent_id, created_by=user.id)
    db.add(folder)
    await db.flush()
    await db.refresh(folder)
    return folder


@router.delete("/folders/{folder_id}")
async def delete_folder(
    folder_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Folder).where(Folder.id == folder_id))
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    await db.delete(folder)
    return {"message": "Folder deleted"}


# ─── Documents ────────────────────────────────────────────────────

@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    folder_id: uuid.UUID | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Document).order_by(Document.created_at.desc())
    if folder_id:
        q = q.where(Document.folder_id == folder_id)
    if search:
        q = q.where(Document.name.ilike(f"%{search}%"))
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    folder_id: str = Form(...),
    name: str = Form(...),
    description: str = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # In production, upload to Supabase Storage
    # For now, store as a placeholder URL
    content = await file.read()
    file_size = len(content)
    file_url = f"/uploads/{uuid.uuid4()}/{file.filename}"

    doc = Document(
        name=name,
        folder_id=uuid.UUID(folder_id),
        file_url=file_url,
        file_size=file_size,
        mime_type=file.content_type or "application/octet-stream",
        description=description,
        uploaded_by=user.id,
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    return doc


@router.delete("/{document_id}")
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await db.delete(doc)
    return {"message": "Document deleted"}
