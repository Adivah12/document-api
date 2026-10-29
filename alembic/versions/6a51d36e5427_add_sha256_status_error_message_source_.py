"""add sha256, status, error_message, source_url

Revision ID: 6a51d36e5427
Revises: f94d0cbf5ab4
Create Date: 2026-10-28 19:53:31.277000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6a51d36e5427'
down_revision: Union[str, Sequence[str], None] = 'f94d0cbf5ab4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("sha256", sa.String(64), nullable=True))
    op.add_column("documents", sa.Column("status", sa.String(), nullable=False, server_default="uploaded"))
    op.add_column("documents", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("source_url", sa.Text(), nullable=True)) 
    op.create_unique_constraint("uq_documents_sha256", "documents", ["sha256"])


def downgrade() -> None:
    op.drop_constraint("uq_documents_sha256", "documents", type_="unique")
    op.drop_column("documents", "source_url")
    op.drop_column("documents", "error_message")
    op.drop_column("documents", "status")
    op.drop_column("documents", "sha256") 
