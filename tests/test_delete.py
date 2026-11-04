"""Pengujian endpoint `DELETE /documents/{document_id}`."""

from pathlib import Path

import io

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session


def _count_documents(db: Session) -> int:
    return db.execute(text("SELECT COUNT(*) FROM documents")).scalar_one()


def test_delete_returns_204(client: TestClient, created_pdf: dict) -> None:
    """Penghapusan yang berhasil harus membalas 204 No Content."""
    response = client.delete(f"/documents/{created_pdf['id']}")

    assert response.status_code == 204, response.text


def test_delete_body_is_empty(client: TestClient, created_pdf: dict) -> None:
    """Respons 204 tidak boleh membawa body."""
    response = client.delete(f"/documents/{created_pdf['id']}")

    assert response.status_code == 204, response.text
    assert response.content == b""


def test_delete_removes_database_row(
    client: TestClient, created_pdf: dict, db_session: Session
) -> None:
    """Baris dokumen harus hilang dari tabel `documents`."""
    assert _count_documents(db_session) == 1

    client.delete(f"/documents/{created_pdf['id']}")

    assert _count_documents(db_session) == 0


def test_delete_removes_file_from_disk(
    client: TestClient, created_pdf: dict, db_session: Session
) -> None:
    """File fisik harus ikut terhapus agar tidak menumpuk di `uploads/`."""
    storage_path = Path(
        db_session.execute(text("SELECT storage_path FROM documents")).scalar_one()
    )
    assert storage_path.is_file()

    client.delete(f"/documents/{created_pdf['id']}")

    assert not storage_path.exists()


def test_delete_unknown_id_returns_404(client: TestClient, random_uuid) -> None:
    """UUID yang tidak ada di database harus menghasilkan 404."""
    response = client.delete(f"/documents/{random_uuid}")

    assert response.status_code == 404


def test_delete_twice_returns_404(client: TestClient, created_pdf: dict) -> None:
    """Menghapus dokumen yang sama dua kali: pertama 204, kedua 404."""
    document_id = created_pdf["id"]

    first = client.delete(f"/documents/{document_id}")
    second = client.delete(f"/documents/{document_id}")

    assert first.status_code == 204
    assert second.status_code == 404


def test_delete_leaves_other_documents(
    client: TestClient, upload_pdf, db_session: Session, pdf_bytes: bytes
) -> None:
    """Menghapus satu dokumen tidak boleh menyentuh dokumen lain."""
    first = upload_pdf("pertama.pdf").json()

    # Dokumen kedua memakai isi berbeda agar tidak terdeteksi sebagai duplikat.
    different_pdf = pdf_bytes + b"\n% berbeda\n"
    second_response = client.post(
        "/document",
        files={"file": ("kedua.pdf", io.BytesIO(different_pdf), "application/pdf")},
    )
    second = second_response.json()
    assert _count_documents(db_session) == 2

    client.delete(f"/documents/{first['id']}")

    assert _count_documents(db_session) == 1
    assert client.get(f"/documents/{second['id']}").status_code == 200