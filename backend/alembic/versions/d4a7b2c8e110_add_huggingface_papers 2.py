"""add huggingface papers

Nueva fuente: papers de Hugging Face (Daily Papers + búsqueda por keywords).
Se guarda abstract y AI summary, no el PDF, y se enlaza a arXiv.

Revision ID: d4a7b2c8e110
Revises: c3f8a1d92e47
Create Date: 2026-10-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4a7b2c8e110"
down_revision: Union[str, Sequence[str], None] = "c3f8a1d92e47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "papers",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=False),
        sa.Column("ai_summary", sa.Text(), nullable=False),
        sa.Column("ai_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("authors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_on_daily_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("upvotes", sa.Integer(), nullable=False),
        sa.Column("comments", sa.Integer(), nullable=False),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("github_repo", sa.Text(), nullable=True),
        sa.Column("project_page", sa.Text(), nullable=True),
        sa.Column("organization", sa.String(length=255), nullable=True),
        sa.Column("linked_models", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("linked_datasets", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("linked_spaces", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("hf_url", sa.Text(), nullable=False),
        sa.Column("arxiv_url", sa.Text(), nullable=False),
        sa.Column("pdf_url", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_papers_published_at", "papers", ["published_at"])
    op.create_index("ix_papers_daily_at", "papers", ["submitted_on_daily_at"])
    op.create_index("ix_papers_upvotes", "papers", ["upvotes"])
    op.create_index("ix_papers_synced_at", "papers", ["synced_at"])

    op.create_table(
        "paper_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("max_results", sa.Integer(), nullable=False),
        sa.Column("days_back", sa.Integer(), nullable=False),
        sa.Column("include_daily", sa.Boolean(), nullable=False),
        sa.Column("include_search", sa.Boolean(), nullable=False),
        sa.Column("last_search_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("paper_config")
    op.drop_index("ix_papers_synced_at", table_name="papers")
    op.drop_index("ix_papers_upvotes", table_name="papers")
    op.drop_index("ix_papers_daily_at", table_name="papers")
    op.drop_index("ix_papers_published_at", table_name="papers")
    op.drop_table("papers")
