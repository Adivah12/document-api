from pydantic_settings import BaseSettings, SettingsConfigDict

from pydantic import field_validator


class Settings(BaseSettings):
    """Konfigurasi aplikasi yang dibaca dari environment variable.

    Nilai diambil dari environment process (mis. compose.yaml) dan,
    untuk pengembangan lokal, bisa juga dari file `.env` di root proyek.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Connection string PostgreSQL dalam format URI.
    # Contoh Supabase (Session pooler):
    # postgresql://postgres.[REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres
    database_url: str

    # Connection string khusus pengujian. WAJIB menunjuk ke database terpisah
    # (contoh: `document_test`), bukan database produksi. Nilai ini divalidasi
    # ulang di `tests/conftest.py` sebelum test dijalankan.
    test_database_url: str | None = None

    @field_validator("test_database_url")
    @classmethod
    def normalize_test_url(cls, value: str | None) -> str | None:
        """Terapkan normalisasi driver yang sama seperti `database_url`."""
        if value is None:
            return None
        return cls.use_psycopg_v3_driver(value)

    @field_validator("database_url")
    @classmethod
    def use_psycopg_v3_driver(cls, value: str) -> str:
        """Pastikan SQLAlchemy memakai psycopg v3, bukan psycopg2.

        Supabase memberi URI `postgresql://...` tanpa nama driver, sedangkan
        SQLAlchemy 2.0 default ke psycopg2 yang tidak terpasang di proyek ini.
        Menambahkan `+psycopg` membuat URI dari dashboard bisa dipakai apa adanya.
        """
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value


settings = Settings()


