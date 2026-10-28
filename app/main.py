import logging
import uuid

from fastapi import Depends,FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from pypdf.errors import PyPdfError
from pathlib import Path

from app.database import get_db
from app.models import Document
from app.pdf_service import extract_pdf_text

logger = logging.getLogger(__name__)

MAX_FILES_SIZE = 10 * 1024 * 1024
UPLOAD_DIR = Path("uploads")

app = FastAPI(
    title="Document API",
    description="API untuk menyimpan dokumen",
    version="1.0.0"
)

@app.get("/health")
def health_check():
    return {"status": "ok",
            "service": "Document API"
    }

@app.get("/health/db")
def database_health_check(db: Session =Depends(get_db)):
    try:
        result = db.execute(text("SELECT 1")).scalar_one()

        return {
            "status": "ok",
            "database": "connected",
            "result": result,
            }
    
    except SQLAlchemyError:
        logger.exception("Pemeriksaan koneksi database gagal")
        raise HTTPException(
            status_code=503,
            detail="Database belum dapat diakses.",
        )

@app.post("/document")
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):

    contens = file.file.read(MAX_FILES_SIZE + 1)
    size_bytes = len(contens)

    if size_bytes == 0:
        raise HTTPException(
            status_code=400,
            detail="File tidak boleh kosong.",
        )

    if size_bytes > MAX_FILES_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Ukuran file maksimal 10 MiB"
        )

    if not contens.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=415,
            detail="Isi file tidak berupa PDF."
        )

    file.file.seek(0)

    document_id = uuid.uuid4()
    storage_path = UPLOAD_DIR / f"{document_id}.pdf"
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        with storage_path.open("xb") as destination:
            destination.write(contens)

    except OSError:
        logger.exception("Penyimpanan PDF gagal")

        raise HTTPException(
            status_code=500,
            detail="File belum dapat disimpan.",
        )

    document = Document(
        id=document_id,
        original_filename=file.filename or "document.pdf",
        storage_path=str(storage_path),
        content_type="application/pdf",
        size_bytes=size_bytes,
    )

    try:
        db.add(document)
        db.commit()

    except SQLAlchemyError:
        db.rollback()
        logger.exception("Penyimpanan metadata dokumen gagal")

        try:
            storage_path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Pembersihan file setelah kegagalan database gagal")

        raise HTTPException(
            status_code=500,
            detail="Metadata dokumen belum dapat disimpan."
        )


    return {
        "id": str(document_id),
        "filename": file.filename,
        "content_type": file.content_type,
        "size_bytes": size_bytes,
        "status": "document_saved",
    }

@app.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    statement = (
        select(Document)
        .order_by(Document.created_at.desc(), Document.id.desc())
        .limit(100)
    )

    documents = db.scalars(statement).all()

    return [
        {
            "id": str(document.id),
            "original_filename": document.original_filename,
            "content_type": document.content_type,
            "size_bytes": document.size_bytes,
            "created_at": document.created_at,
        }
        for document in documents
    ]

@app.get("/documents/{document_id}")
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Dokumen tidak ditemukan.",
        )

    return{
        "id": str(document.id),
        "original_filename": document.original_filename,
        "content_type": document.content_type,
        "size_bytes": document.size_bytes,
        "created_at": document.created_at,
    }

@app.get("/documents/{document_id}/download")
def download_content(
    document_id: uuid.UUID,
    db: Session = Depends(get_db), 
):
    document = db.get(Document,document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Dokumen tidak ditemukan.",
        )

    storage_path = Path(document.storage_path)

    if not storage_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="File PDF tidak ditemukan di penyimpanan."
        )

    return FileResponse(
        path=storage_path,
        media_type="application/pdf",
        filename=document.original_filename,
    )

@app.get("/documents/{document_id}/text")
def get_document_text(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Dokumen tidak ditemukan.",
        )

    if document.extracted_text is None:
        raise HTTPException(
            status_code=409,
            detail=(
                    "Teks dokumen belum diekstrak. "
                    "Jalankan POST /documents/{document_id}/extract terlebih dahulu."
        ),
    )

    return {
        "id":str(document.id),
        "original_filename": document.original_filename,
        "character_count": len(document.extracted_text),
        "text": document.extracted_text,
    }

@app.post("/documents/{document_id}/extract")
def extract_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Dokumen tidak ditemukan.",
        )

    storage_path = Path(document.storage_path)

    if not storage_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="File PDF tidak ditemukan di penyimpanan.",
        )

    try:
        extracted_text = extract_pdf_text(str(storage_path))

    except PyPdfError:
        logger.exception("Pembacaan PDF gagal")

        raise HTTPException(
            status_code=422,
            detail="PDF tidak dapat dibaca. File mungkin rusak atau terenskripsi.",
        )

    except OSError:
        logger.exception("Akses file PDF gagal")

        raise HTTPException(
            status_code=500,
            detail="File PDF belum dapat diakses.",
        )

    document.extracted_text = extracted_text

    try:
        db.commit()

    except SQLAlchemyError:
        db.rollback()
        logger.exception("Penyimpanan teks dokumen gagal")

        raise HTTPException(
            status_code=500,
            detail="Teks dokumen belum dapat disimpan.",
        )

    return {
        "id": str(document_id),
        "character_count": len(extracted_text),
        "status": "text_saved",
    }