"""Konfigurasi pytest untuk Document API.

Pengujian berjalan di **database PostgreSQL terpisah** (`TEST_DATABASE_URL`,
contoh `document_test`) pada instance Supabase yang sama. Skema dibuat lewat
migrasi Alembic, sehingga test sekaligus memvalidasi jalur migrasi yang akan
dipakai produksi.
"""

from __future__ import annotations

import io
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import get_db
from app.main import app as fastapi_app

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# PDF minimal yang valid: punya tabel xref dan trailer lengkap agar pypdf bisa
# membaca satu halaman berisi teks. Fungsi di bawah menyusun offset xref secara
# otomatis supaya berkas benar-benar sah menurut spesifikasi PDF.
def _build_minimal_pdf(text: str = "Halo NusaDesk") -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length __LEN__ >>\nstream\n__STREAM__\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode("latin-1")
    objects[3] = objects[3].replace(b"__LEN__", str(len(stream)).encode()).replace(
        b"__STREAM__", stream
    )

    buffer = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []

    for number, body in enumerate(objects, start=1):
        offsets.append(len(buffer))
        buffer += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"

    startxref = len(buffer)
    buffer += f"xref\n0 {len(objects) + 1}\n".encode()
    buffer += b"0000000000 65535 f \n"
    for offset in offsets:
        buffer += f"{offset:010d} 00000 n \n".encode()

    buffer += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{startxref}\n%%EOF\n"
    ).encode()

    return bytes(buffer)


MINIMAL_PDF = _build_minimal_pdf()

PDF_BYTES = MINIMAL_PDF
TXT_BYTES = b"Selamat datang di NusaDesk. Dokumen contoh untuk pengujian."
TXT_BYTES_WITH_BOM = b"\xef\xbb\xbf" + b"Teks berawalan BOM."
EMPTY_BYTES = b""
BINARY_BYTES = b"\x00\x01\x02\xff\xfe\x89\x50\x12\x34"

OVERSIZED_BYTES = b"%PDF-" + b"A" * (10 * 1024 * 1024 + 1)

def _upload(client, content, filename, content_type="application/octet-stream"):
    return client.post(
        "/document",
        files={"file": (filename, io.BytesIO(content), content_type)},
    )

@pytest.fixture()
def pdf_bytes() -> bytes:
    return PDF_BYTES

@pytest.fixture()
def txt_bytes() -> bytes:
    return TXT_BYTES

@pytest.fixture()
def txt_bytes_with_bom() -> bytes:
    return TXT_BYTES_WITH_BOM

@pytest.fixture()
def binary_bytes() -> bytes:
    return BINARY_BYTES

@pytest.fixture()
def empty_bytes() -> bytes:
    return EMPTY_BYTES

@pytest.fixture()
def oversized_bytes() -> bytes:
    return OVERSIZED_BYTES

@pytest.fixture()
def upload_pdf(client, pdf_bytes):
    def _do(filename="contoh.pdf"):
        return _upload(client, pdf_bytes, filename, "application/pdf")
    return _do

@pytest.fixture()
def upload_txt(client, txt_bytes):
    def _do(filename="contoh.txt", content=None):
        content = content if content is not None else txt_bytes
        return _upload(client, content, filename, "text/plain")
    return _do

@pytest.fixture()
def created_pdf(client, upload_pdf) -> dict:
    response = upload_pdf()
    assert response.status_code == 201, response.text
    return response.json()

@pytest.fixture()
def random_uuid():
    return uuid.uuid4()


def _require_safe_test_url() -> str:
    """Ambil URL database test dan pastikan tidak menunjuk database produksi.

    Ini pertahanan terakhir: bila `.env` salah konfigurasi (mis. menunjuk ke
    database `postgres` produksi), pengujian dibatalkan sebelum satu pun tabel
    disentuh.
    """
    url = settings.test_database_url

    if not url:
        pytest.exit(
            "TEST_DATABASE_URL belum diset. Tambahkan ke `.env`, contoh:\n"
            "  TEST_DATABASE_URL=postgresql://user:pass@host:5432/document_test",
            returncode=2,
        )

    database_name = url.rsplit("/", 1)[-1].lower()

    if "test" not in database_name:
        pytest.exit(
            "TEST_DATABASE_URL tidak memakai database dengan kata 'test'. "
            "Pengujian dibatalkan demi keamanan data produksi.\n"
            f"  nama database terbaca: {database_name!r}",
            returncode=2,
        )

    return url


@pytest.fixture(scope="session")
def test_database_url() -> str:
    return _require_safe_test_url()


@pytest.fixture(scope="session")
def engine(test_database_url: str) -> Generator[Engine, None, None]:
    """Engine ke database test.

    `NullPool` dipakai agar setiap koneksi ditutup begitu selesai — Supabase
    free tier membatasi jumlah koneksi bersamaan, sementara pytest membuka
    banyak sesi berurutan.
    """
    test_engine = create_engine(
        test_database_url,
        pool_pre_ping=True,
        poolclass=NullPool,
        connect_args={"connect_timeout": 10},
    )
    yield test_engine
    test_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def migrated_schema(engine: Engine) -> Generator[None, None, None]:
    """Bangun skema lewat Alembic, bukan `metadata.create_all()`.

    Memakai migrasi membuat test sekaligus memverifikasi bahwa rantai migrasi
    benar-benar bisa membangun skema dari nol — persis yang terjadi di produksi.
    """
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option(
        "sqlalchemy.url", engine.url.render_as_string(hide_password=False)
    )

    command.downgrade(config, "base")
    command.upgrade(config, "head")

    yield


@pytest.fixture()
def db_session(engine: Engine) -> Generator[Session, None, None]:
    """Sesi database terisolasi untuk satu test."""
    factory = sessionmaker(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(autouse=True)
def clean_tables(db_session: Session) -> Generator[None, None, None]:
    """Kosongkan tabel `documents` sebelum setiap test.

    `TRUNCATE` dipakai (bukan `DELETE`) karena lebih cepat dan sekaligus
    mereset sequence — perilaku khas PostgreSQL.
    """
    db_session.execute(text("TRUNCATE TABLE documents RESTART IDENTITY CASCADE"))
    db_session.commit()
    yield


@pytest.fixture()
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Arahkan penyimpanan file ke direktori sementara.

    Tanpa ini, setiap test akan meninggalkan file di folder `uploads/` proyek.
    """
    target = tmp_path / "uploads"
    target.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("app.main.UPLOAD_DIR", target)
    return target


@pytest.fixture()
def client(db_session: Session, upload_dir: Path) -> Generator[TestClient, None, None]:
    """`TestClient` yang memakai sesi database test, bukan database produksi."""

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db

    with TestClient(fastapi_app) as test_client:
        yield test_client

    fastapi_app.dependency_overrides.clear()
