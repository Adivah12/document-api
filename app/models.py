import uuid

from datetime import datetime
from sqlalchemy import BigInteger,Text, Uuid, DateTime, func, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    original_filename : Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    storage_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    content_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    extracted_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    sha256: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(),
        nullable=False,
        default="uploaded",
        server_default="uploaded"
    )

    error_message: Mapped [str | None] = mapped_column(
        Text,
        nullable=True
    )

    source_url: Mapped [str | None] = mapped_column(
        Text,
        nullable=True
    )