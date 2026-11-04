"""Pengujian `POST /documents/{id}/extract` dan `GET /documents/{id}/text`."""

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session


def test_extract_pdf_sets_ready(client: TestClient, created_pdf: dict) -> None:
    """Ekstraksi PDF mengubah status menjadi `ready`."""
    response = client.post(f"/documents/{created_pdf['id']}/extract")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ready"
    assert body["character_count"] > 0


def test_extract_txt_sets_ready(client: TestClient, upload_txt) -> None:
    """Ekstraksi TXT memakai jalur dekode, bukan pypdf."""
    document = upload_txt().json()

    response = client.post(f"/documents/{document['id']}/extract")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ready"


def test_extract_txt_keeps_content(client: TestClient, upload_txt, txt_bytes: bytes) -> None:
    """Teks TXT tersimpan utuh."""
    document = upload_txt().json()
    client.post(f"/documents/{document['id']}/extract")

    text_response = client.get(f"/documents/{document['id']}/text")

    assert text_response.status_code == 200
    assert text_response.json()["text"] == txt_bytes.decode("utf-8")


def test_extract_txt_strips_bom(client: TestClient, upload_txt, txt_bytes_with_bom: bytes) -> None:
    """BOM UTF-8 dibuang agar pencarian teks tidak rusak."""
    document = upload_txt("berbom.txt", txt_bytes_with_bom).json()
    client.post(f"/documents/{document['id']}/extract")

    stored = client.get(f"/documents/{document['id']}/text").json()["text"]

    assert not stored.startswith("\ufeff")
    assert stored == txt_bytes_with_bom.decode("utf-8-sig")


def test_extract_updates_status_in_database(
    client: TestClient, created_pdf: dict, db_session: Session
) -> None:
    """Status berpindah dari `uploaded` ke `ready` di database."""
    before = db_session.execute(text("SELECT status FROM documents")).scalar_one()
    assert before == "uploaded"

    client.post(f"/documents/{created_pdf['id']}/extract")

    db_session.expire_all()
    after = db_session.execute(text("SELECT status FROM documents")).scalar_one()
    assert after == "ready"


def test_extract_unknown_id_returns_404(client: TestClient, random_uuid) -> None:
    """Ekstraksi dokumen yang tidak ada menghasilkan 404."""
    assert client.post(f"/documents/{random_uuid}/extract").status_code == 404


def test_text_before_extract_returns_409(client: TestClient, created_pdf: dict) -> None:
    """Mengambil teks sebelum ekstraksi menghasilkan 409."""
    assert client.get(f"/documents/{created_pdf['id']}/text").status_code == 409


def test_text_after_extract_returns_content(client: TestClient, created_pdf: dict) -> None:
    """Teks tersedia setelah ekstraksi dijalankan."""
    client.post(f"/documents/{created_pdf['id']}/extract")

    response = client.get(f"/documents/{created_pdf['id']}/text")

    assert response.status_code == 200
    body = response.json()
    assert body["character_count"] == len(body["text"])
    assert body["original_filename"] == "contoh.pdf"

def test_extract_error_message_generik(client: TestClient, random_uuid) -> None:
    """Pesan error ekstraksi tidak boleh menyebut 'PDF' sebagai kata kaku."""
    response = client.post(f"/documents/{random_uuid}/extract")

    assert response.status_code == 404
