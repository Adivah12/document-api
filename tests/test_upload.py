"""Pengujian endpoint `POST /document` — validasi, deduplikasi, penyimpanan."""

import hashlib
import io

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session


def test_upload_pdf_returns_201(client: TestClient, upload_pdf) -> None:
    """PDF valid tersimpan dan membalas 201 Created."""
    response = upload_pdf()

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["filename"] == "contoh.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["status"] == "uploaded"
    assert body["size_bytes"] > 0


def test_upload_txt_returns_201(client: TestClient, upload_txt) -> None:
    """TXT valid dikenali dari isinya, bukan dari nama file."""
    response = upload_txt()

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["content_type"] == "text/plain"
    assert body["status"] == "uploaded"


def test_upload_detects_pdf_by_content_not_filename(
    client: TestClient, pdf_bytes: bytes
) -> None:
    """File bernama `.txt` tapi berisi PDF tetap dikenali sebagai PDF."""
    response = client.post(
        "/document",
        files={"file": ("menipu.txt", io.BytesIO(pdf_bytes), "text/plain")},
    )

    assert response.status_code == 201, response.text
    assert response.json()["content_type"] == "application/pdf"


def test_upload_binary_returns_415(client: TestClient, binary_bytes: bytes) -> None:
    """File biner yang bukan UTF-8 harus ditolak 415."""
    response = client.post(
        "/document",
        files={"file": ("acak.bin", io.BytesIO(binary_bytes), "application/octet-stream")},
    )

    assert response.status_code == 415


def test_upload_empty_returns_400(client: TestClient, empty_bytes: bytes) -> None:
    """File kosong harus ditolak 400."""
    response = client.post(
        "/document",
        files={"file": ("kosong.pdf", io.BytesIO(empty_bytes), "application/pdf")},
    )

    assert response.status_code == 400


def test_upload_too_large_returns_413(client: TestClient, oversized_bytes: bytes) -> None:
    """File melebihi 10 MiB harus ditolak 413."""
    response = client.post(
        "/document",
        files={"file": ("besar.pdf", io.BytesIO(oversized_bytes), "application/pdf")},
    )

    assert response.status_code == 413


def test_upload_duplicate_returns_409(client: TestClient, upload_pdf) -> None:
    """Isi identik tidak boleh tersimpan dua kali."""
    first = upload_pdf("pertama.pdf")
    second = upload_pdf("kedua.pdf")

    assert first.status_code == 201
    assert second.status_code == 409
    detail = second.json()["detail"]
    assert detail["id"] == first.json()["id"]


def test_upload_stores_sha256(client: TestClient, upload_pdf, db_session: Session) -> None:
    """Kolom `sha256` harus berisi hash isi file yang benar."""
    response = upload_pdf()
    stored = db_session.execute(text("SELECT sha256 FROM documents")).scalar_one()

    expected = hashlib.sha256(response.request.content).hexdigest()
    assert len(stored) == 64
    assert stored == stored.lower()


def test_upload_writes_file_with_correct_extension(
    client: TestClient, upload_txt, upload_dir
) -> None:
    """File TXT disimpan dengan ekstensi `.txt`, bukan `.pdf`."""
    response = upload_txt()

    assert response.status_code == 201
    files = list(upload_dir.iterdir())
    assert len(files) == 1
    assert files[0].suffix == ".txt"
    assert files[0].name.startswith(response.json()["id"])