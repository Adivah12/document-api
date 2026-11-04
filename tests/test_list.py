"""Pengujian `GET /documents` — pagination dan total."""

import io

from fastapi.testclient import TestClient


def _upload_n(client: TestClient, pdf_bytes: bytes, count: int) -> list[dict]:
    """Unggah `count` PDF berbeda isi agar tidak terdeteksi duplikat."""
    results = []
    for index in range(count):
        content = pdf_bytes + f"\n% varian {index}\n".encode()
        response = client.post(
            "/document",
            files={"file": (f"doc{index}.pdf", io.BytesIO(content), "application/pdf")},
        )
        assert response.status_code == 201, response.text
        results.append(response.json())
    return results


def test_list_empty_returns_zero_total(client: TestClient) -> None:
    """Database kosong tetap membalas struktur lengkap dengan total 0."""
    response = client.get("/documents")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}


def test_list_default_pagination(client: TestClient, created_pdf: dict) -> None:
    """Nilai default pagination adalah limit 20 dan offset 0."""
    body = client.get("/documents").json()

    assert body["limit"] == 20
    assert body["offset"] == 0
    assert body["total"] == 1
    assert len(body["items"]) == 1


def test_list_limit_and_offset(client: TestClient, pdf_bytes: bytes) -> None:
    """`limit` dan `offset` benar-benar membatasi hasil, tanpa tumpang tindih."""
    _upload_n(client, pdf_bytes, 3)

    first = client.get("/documents?limit=1&offset=0").json()
    second = client.get("/documents?limit=1&offset=1").json()

    assert first["total"] == 3
    assert len(first["items"]) == 1
    assert len(second["items"]) == 1
    assert first["items"][0]["id"] != second["items"][0]["id"]


def test_list_newest_first(client: TestClient, pdf_bytes: bytes) -> None:
    """Dokumen terbaru muncul lebih dulu."""
    created = _upload_n(client, pdf_bytes, 2)

    items = client.get("/documents").json()["items"]

    assert items[0]["id"] == created[-1]["id"]
    assert items[1]["id"] == created[0]["id"]


def test_list_invalid_limit_returns_422(client: TestClient) -> None:
    """`limit` di luar batas validasi Pydantic ditolak 422."""
    assert client.get("/documents?limit=500").status_code == 422


def test_list_negative_offset_returns_422(client: TestClient) -> None:
    """`offset` negatif ditolak 422."""
    assert client.get("/documents?offset=-1").status_code == 422


def test_list_items_have_no_extracted_text(
    client: TestClient, created_pdf: dict, pdf_bytes: bytes
) -> None:
    """Daftar hanya memuat metadata, bukan teks hasil ekstraksi."""
    item = client.get("/documents").json()["items"][0]

    assert set(item) == {
        "id",
        "original_filename",
        "content_type",
        "size_bytes",
        "created_at",
    }