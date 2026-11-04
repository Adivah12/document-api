# Document API — Backend Ingesti Dokumen untuk RAG

![CI](https://github.com/USERNAME/document-api/actions/workflows/ci.yml/badge.svg)

REST API untuk **mengunggah, memvalidasi, menyimpan, dan mengekstrak teks dari dokumen**. FastAPI menangani request dan validasi, PostgreSQL menyimpan metadata dan teks hasil ekstraksi, file asli disimpan di disk. Proyek ini adalah **Fase 1** dari Document RAG Assistant — teks yang sudah bersih siap masuk ke tahap chunking → embedding → RAG.

> [!NOTE]
> Repositori ini telah **dipindahkan dari Docker PostgreSQL lokal ke Supabase** (PostgreSQL 17.11 hosted). Docker Compose masih tersedia sebagai fallback offline / pengujian lokal.

---

## 📋 Daftar Isi

- [🎯 Tujuan & Manfaat](#-tujuan--manfaat)
- [🚀 Mulai Cepat](#-mulai-cepat)
- [🔌 Koneksi Database](#-koneksi-database)
- [🗄️ Endpoint](#️-endpoint)
- [🧪 Pengujian](#-pengujian)
- [🗂️ Struktur Project](#️-struktur-project)
- [🔒 Keamanan](#-keamanan)
- [📊 Status Roadmap](#-status-roadmap)
- [🤝 Kontribusi](#-kontribusi)

---
## 🎯 Tujuan & Manfaat

| Tujuan Teknis | Deskripsi |
|---|---|
| **Ingesti dokumen** | Satu endpoint menerima file dari berbagai sumber dan menyimpannya secara terstruktur |
| **Validasi berlapis** | Menolak file berukuran berlebihan, format salah, atau ekstensi yang tidak cocok dengan isi |
| **Deteksi duplikat** | Hash SHA-256 mencegah dokumen sama tersimpan berkali-kali (respons `409`) |
| **Ekstraksi teks** | Menyediakan teks bersih dari PDF dan TXT sebagai bahan mentah tahap RAG |
| **Fondasi yang bisa diuji** | 46 automated test dengan pytest, semua hijau |

### Nilai Portofolio

Desain API yang matang: kontrak endpoint, status code yang tepat (`201`, `409`, `415`, `204`), validasi berlapis, deduplikasi, migrasi skema Alembic, dan orkestrasi multi-service lewat Docker.
## 🚀 Mulai Cepat

### Prasyarat

- Python 3.12+
- PostgreSQL (Supabase atau Docker lokal)
- Git

### 1. Clone repositori

```bash
git clone https://github.com/username/document-api.git
cd document-api
```

### 2. Buat environment virtual dan instal dependensi

```bash
python -m venv .venv
.\.venv\Scripts\activate        # Windows PowerShell
# atau
source .venv/bin/activate       # Linux/macOS

pip install -r requirements.txt
```

### 3. Konfigurasi `.env`

```bash
copy .env.example .env    # Windows
# atau
cp .env.example .env      # Linux/macOS
```

Edit `.env` dan isi `DATABASE_URL` serta `TEST_DATABASE_URL` dengan nilai Anda sendiri:

```env
DATABASE_URL=postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres
TEST_DATABASE_URL=postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/document_test
```

> [!WARNING]
> **JANGAN commit `.env`**. File ini sudah diabaikan oleh `.gitignore` dan berisi kredensial rahasia.
## 🔌 Koneksi Database

### Produksi (Supabase)

`DATABASE_URL` menunjuk ke database utama. Format dari dashboard Supabase bisa disalin **apa adanya** — validator di `app/config.py` otomatis menambahkan `+psycopg` sehingga SQLAlchemy menggunakan driver psycopg v3.

### Pengujian (`document_test`)

`TEST_DATABASE_URL` harus menunjuk ke **database terpisah** (`document_test`), bukan produksi. Fixture pytest akan:

1. Membangun skema lewat **migrasi Alembic** (`downgrade base` → `upgrade head`)
2. Mengosongkan tabel `documents` sebelum setiap test (`TRUNCATE ... RESTART IDENTITY`)
3. Membatalkan jalan bila URL tidak mengandung kata `"test"` (pengaman terakhir)
## 🗄️ Endpoint

| Method | Endpoint | Status | Deskripsi |
|---|---|---|---|
| `GET` | `/health` | `200` | Cek kesehatan aplikasi |
| `GET` | `/health/db` | `200` | Cek koneksi database |
| `POST` | `/document` | `201` | Unggah dokumen (PDF atau TXT) |
| `GET` | `/documents` | `200` | Daftar dokumen dengan pagination |
| `GET` | `/documents/{id}` | `200` | Metadata satu dokumen |
| `GET` | `/documents/{id}/download` | `200` | Unduh file asli (byte-identik) |
| `POST` | `/documents/{id}/extract` | `200` | Ekstrak teks (`uploaded → ready`) |
| `GET` | `/documents/{id}/text` | `200` | Ambil hasil ekstraksi |
| `DELETE` | `/documents/{id}` | `204` | Hapus dokumen + file dari disk |

### Contoh Respons

**Upload berhasil (`201`)**

```json
{
  "id": "a167351a-9f99-48d5-ba9d-ca2cba9e1c55",
  "filename": "01_Kebijakan_Cuti.pdf",
  "content_type": "application/pdf",
  "size_bytes": 4805,
  "status": "uploaded"
}
```

**Duplikat (`409`)**

```json
{
  "detail": {
    "message": "dokumen sudah pernah diunggah.",
    "id": "a167351a-9f99-48d5-ba9d-ca2cba9e1c55"
  }
}
```

**Pagination (`GET /documents`)**

```json
{
  "items": [
    {
      "id": "33a3ea2a-8dbe-4cf0-8fe6-190bf6d59515",
      "original_filename": "02_SOP_Reimbursement.pdf",
      "content_type": "application/pdf",
      "size_bytes": 4779,
      "created_at": "2026-10-28T17:54:03.656090+00:00"
    }
  ],
  "total": 2,
  "limit": 20,
  "offset": 0
}
```

**Ekstraksi teks (`200`)**

```json
{
  "id": "c9aebb42-ea68-4719-987d-8d03618014b1",
  "character_count": 3921,
  "status": "ready"
}
```
## 🧪 Pengujian

Project menggunakan **pytest** dengan 46 automated test.

```bash
.\.venv\Scripts\python.exe -m pytest -v        # semua test
.\.venv\Scripts\python.exe -m pytest tests/test_delete.py -v   # hanya DELETE
.\.venv\Scripts\python.exe -m pytest -x -v       # berhenti di gagal pertama
```

### Cakupan Test

| File | Jumlah | Cakupan |
|---|---|---|
| `test_health.py` | 2 | `/health`, `/health/db` |
| `test_upload.py` | 9 | `201`, `400`, `409`, `413`, `415`, magic bytes, SHA-256, ekstensi file |
| `test_list.py` | 7 | pagination `limit`/`offset`/`total`, urutan, validasi `422` |
| `test_detail.py` | 8 | metadata, `404`, UUID invalid, download byte-identik, `Content-Type` |
| `test_extract.py` | 8 | PDF/TXT, BOM UTF-8, transisi status DB, `409` sebelum ekstraksi |
| `test_delete.py` | 7 | `204`, body kosong, hapus baris DB, hapus file disk, `404` |
| `test_extractor.py` | 4 | unit test fungsi ekstraksi teks |

### Desain Pengujian

- **Database terpisah** — test berjalan di `document_test`, **tidak pernah** menyentuh produksi
- **Migrasi Alembic** — skema dibangun lewat `alembic upgrade head`, bukan `create_all()`
- **Isolasi file** — upload test diarahkan ke `tmp_path`, tidak menumpuk di `uploads/`
- **NullPool** — mencegah habisnya kuota koneksi Supabase free tier
## 🗂️ Struktur Project

```
document-api/
├── alembic/                    # Migrasi database
│   ├── env.py                  # Konfigurasi Alembic (diperbaiki untuk honour sqlalchemy.url)
│   └── versions/
├── app/
│   ├── __init__.py
│   ├── config.py               # Pydantic Settings + validator DATABASE_URL
│   ├── database.py             # SQLAlchemy engine + SessionLocal
│   ├── main.py                 # FastAPI app + semua endpoint
│   ├── models.py               # Model Document (SQLAlchemy)
│   ├── pdf_service.py          # Ekstraksi teks PDF (pypdf)
│   └── services/
│       └── text_extractor.py   # Ekstraksi teks TXT (utf-8-sig)
├── tests/
│   ├── conftest.py             # 15 fixture pytest
│   ├── test_*.py               # 46 automated test
│   └── __init__.py
├── sample_documents/           # 5 file PDF contoh
├── uploads/                    # Penyimpanan file di disk (diabaikan Git)
├── .env                        # Kredensial (JANGAN commit)
├── .env.example                # Template konfigurasi
├── compose.yaml                # Docker Compose (db + api)
├── Dockerfile
├── pytest.ini
├── requirements.txt
└── README.MD
```

## 🔒 Keamanan

| Aspek | Kebijakan |
|---|---|
| `.env` | **JANGAN commit**. Sudah diabaikan `.gitignore` |
| Password Supabase | Sudah pernah ter-expose di output obrolan — **segera rotasi** di dashboard Supabase |
| `TEST_DATABASE_URL` | Wajib berbeda dari `DATABASE_URL`; pengaman menolak jalan bila nama database tidak mengandung `"test"` |
| Autentikasi | Belum ada — fokus tahap 1 pada inti functionality. Tambahkan auth sebelum expose publik |

## 📊 Status Roadmap

| # | Tugas | Status |
|---|---|---|
| 1 | Setup Supabase | ✅ Selesai |
| 2 | Config & `.env` | ✅ Selesai |
| 3 | Migrasi kolom `sha256`, `status`, `error_message`, `source_url` | ✅ Selesai |
| 4 | Deteksi PDF/TXT via magic bytes + 415 | ✅ Selesai |
| 5 | Dedup SHA-256 + respons `409` | ✅ Selesai |
| 6 | `DELETE /documents/{id}` (204) | ✅ Selesai + 7 test |
| 7 | Pagination `limit`/`offset`/`total` | ✅ Selesai |
| 8 | Tests pytest (46 test) | ✅ Selesai |
| 9 | README | ✅ Selesai (file ini) |
| 10 | Rotasi password Supabase | ⏳ Belum — **urgent** |

## 🤝 Kontribusi

1. Fork repositori
2. Buat branch fitur (`git checkout -b fitur/nama`)
3. Commit perubahan (`git commit -m "feat: deskripsi"`)
4. Push ke branch (`git push origin fitur/nama`)
5. Buka Pull Request

Pastikan semua test lulus sebelum mengajukan PR:

```bash
.\.venv\Scripts\python.exe -m pytest -q
```

## 📄 Lisensi

MIT License. Lihat file `LICENSE` untuk detailnya.