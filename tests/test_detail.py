"""Pengujian `GET /documents/{id}` dan `GET /documents/{id}/download`."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session


def test_get_detail_returns_metadata(client: TestClient, created_pdf: dict) -> None:
    """Detail dokumen memuat metadata lengkap."""
    response = client.get(f"/documents/{created_pdf['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created_pdf["id"]
    assert body["original_filename"] == "contoh.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size_bytes"] == created_pdf["size_bytes"]
    assert body["created_at"]


def test_get_detail_unknown_id_returns_404(client: TestClient, random_uuid) -> None:
    """UUID yang tidak ada menghasilkan 404."""
    assert client.get(f"/documents/{random_uuid}").status_code == 404


def test_get_detail_invalid_uuid_returns_422(client: TestClient) -> None:
    """UUID yang formatnya salah ditolak validasi path 422."""
    assert client.get("/documents/bukan-uuid").status_code == 422


def test_download_returns_identical_bytes(
    client: TestClient, created_pdf: dict, pdf_bytes: bytes
) -> None:
    """Isi file yang diunduh harus identik byte-per-byte dengan yang diunggah."""
    response = client.get(f"/documents/{created_pdf['id']}/download")

    assert response.status_code == 200
    assert response.content == pdf_bytes


def test_download_unknown_id_returns_404(client: TestClient, random_uuid) -> None:
    """Mengunduh dokumen yang tidak ada menghasilkan 404."""
    assert client.get(f"/documents/{random_uuid}/download").status_code == 404


def test_download_pdf_returns_pdf_content_type(client: TestClient, created_pdf: dict) -> None:
    """Download PDF harus mengirim Content-Type application/pdf."""
    response = client.get(f"/documents/{created_pdf['id']}/download")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"


def test_download_txt_returns_txt_content_type(client: TestClient, upload_txt) -> None:
    """Download TXT harus mengirim Content-Type text/plain."""
    document = upload_txt("contoh.txt").json()

    response = client.get(f"/documents/{document['id']}/download")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")


def test_download_missing_file_mentions_correct_type(
    client: TestClient, upload_txt, db_session: Session
) -> None:
    """Pesan 404 harus menyebutkan tipe file yang benar, tidak selalu 'PDF'."""
    document = upload_txt("contoh.txt").json()

    storage_path = Path(
        db_session.execute(text("SELECT storage_path FROM documents")).scalar_one()
    )

    storage_path.unlink(missing_ok=True)

    response = client.get(f"/documents/{document['id']}/download")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert "File TXT tidak ditemukan di penyimpanan." in detail

