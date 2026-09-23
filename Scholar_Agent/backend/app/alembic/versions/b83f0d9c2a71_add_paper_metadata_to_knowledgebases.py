"""Add paper metadata to knowledgebases

Revision ID: b83f0d9c2a71
Revises: 43c6db52e840
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b83f0d9c2a71"
down_revision: Union[str, None] = "43c6db52e840"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add bibliographic and personal-management fields to papers."""
    op.add_column(
        "knowledgebases",
        sa.Column("title", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "knowledgebases",
        sa.Column(
            "authors",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "knowledgebases",
        sa.Column("year", sa.Integer(), nullable=True),
    )
    op.add_column(
        "knowledgebases",
        sa.Column("venue", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "knowledgebases",
        sa.Column("doi", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "knowledgebases",
        sa.Column(
            "keywords",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "knowledgebases",
        sa.Column("abstract", sa.Text(), nullable=True),
    )
    op.add_column(
        "knowledgebases",
        sa.Column("research_topic", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "knowledgebases",
        sa.Column(
            "read_status",
            sa.String(length=32),
            server_default=sa.text("'unread'"),
            nullable=False,
        ),
    )
    op.add_column(
        "knowledgebases",
        sa.Column(
            "personal_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )

    op.create_check_constraint(
        "ck_knowledgebases_read_status",
        "knowledgebases",
        "read_status IN ('unread', 'reading', 'read', 'archived')",
    )
    op.create_check_constraint(
        "ck_knowledgebases_year",
        "knowledgebases",
        "year IS NULL OR (year >= 1000 AND year <= 9999)",
    )
    op.create_index(
        "idx_knowledgebases_read_status",
        "knowledgebases",
        ["read_status"],
    )
    op.create_index(
        "idx_knowledgebases_year",
        "knowledgebases",
        ["year"],
    )
    op.create_index(
        "idx_knowledgebases_doi",
        "knowledgebases",
        ["doi"],
    )


def downgrade() -> None:
    """Remove paper metadata from knowledgebases."""
    op.drop_index("idx_knowledgebases_doi", table_name="knowledgebases")
    op.drop_index("idx_knowledgebases_year", table_name="knowledgebases")
    op.drop_index("idx_knowledgebases_read_status", table_name="knowledgebases")
    op.drop_constraint(
        "ck_knowledgebases_year", "knowledgebases", type_="check"
    )
    op.drop_constraint(
        "ck_knowledgebases_read_status", "knowledgebases", type_="check"
    )

    op.drop_column("knowledgebases", "personal_tags")
    op.drop_column("knowledgebases", "read_status")
    op.drop_column("knowledgebases", "research_topic")
    op.drop_column("knowledgebases", "abstract")
    op.drop_column("knowledgebases", "keywords")
    op.drop_column("knowledgebases", "doi")
    op.drop_column("knowledgebases", "venue")
    op.drop_column("knowledgebases", "year")
    op.drop_column("knowledgebases", "authors")
    op.drop_column("knowledgebases", "title")
