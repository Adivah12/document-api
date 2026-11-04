"""Unit test untuk fungsi ekstraksi teks (tanpa HTTP, tanpa database)."""

from pathlib import Path

import pytest

from app.pdf_service import extract_pdf_text
from app.services.text_extractor import extract_txt_text


def test_extract_pdf_text_reads_content(tmp_path: Path, pdf_bytes: bytes) -> None:
    """Teks PDF terbaca dan hasilnya berupa string."""
    pdf_path = tmp_path / "contoh.pdf"
    pdf_path.write_bytes(pdf_bytes)

    result = extract_pdf_text(str(pdf_path))

    assert isinstance(result, str)
    assert "Halo NusaDesk" in result


def test_extract_txt_text_reads_content(tmp_path: Path, txt_bytes: bytes) -> None:
    """Teks TXT terbaca utuh."""
    txt_path = tmp_path / "contoh.txt"
    txt_path.write_bytes(txt_bytes)

    assert extract_txt_text(str(txt_path)) == txt_bytes.decode("utf-8")


def test_extract_txt_text_strips_bom(tmp_path: Path, txt_bytes_with_bom: bytes) -> None:
    """BOM UTF-8 dibuang dari awal berkas."""
    txt_path = tmp_path / "berbom.txt"
    txt_path.write_bytes(txt_bytes_with_bom)

    result = extract_txt_text(str(txt_path))

    assert not result.startswith("\ufeff")
    assert result == txt_bytes_with_bom.decode("utf-8-sig")


def test_extract_pdf_text_raises_on_missing_file(tmp_path: Path) -> None:
    """Berkas yang tidak ada harus memunculkan OSError."""
    with pytest.raises(OSError):
        extract_pdf_text(str(tmp_path / "tidak-ada.pdf"))