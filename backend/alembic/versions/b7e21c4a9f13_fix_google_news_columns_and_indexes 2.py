"""fix google news columns, add indexes and github detail fields

Motivo: el sync de Google News fallaba con
`value too long for type character varying(512)` porque el `guid` del RSS de
Google es un token opaco de hasta ~800 caracteres que se usaba como primary key.
Esta migracion:

- `google_news_articles.id` pasa a VARCHAR(64): ahora guarda un sha1 del link
  (la app ya lo genera asi).
- `google_news_articles.link` / `source_url` / `image_url` pasan a TEXT: el link
  opaco + query string no cabe en VARCHAR(512).
- Anade `original_link` y `content_fetched` para saber si el cuerpo del
  articulo se pudo extraer y poder reintentar la decodificacion de la URL.
- Anade `days_window` a la config de News (filtro "de ese dia").
- Anade campos de detalle a `github_repos` (watchers, homepage, size, rama).
- Crea los indices que usan los ORDER BY del feed.

Es no destructiva: solo ensancha columnas y agrega indices.

Revision ID: b7e21c4a9f13
Revises: 30fdea0ce3b3
Create Date: 2026-10-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7e21c4a9f13"
down_revision: Union[str, Sequence[str], None] = "30fdea0ce3b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Google News: el guid opaco no cabe en VARCHAR(512) ──
    op.alter_column(
        "google_news_articles",
        "id",
        existing_type=sa.String(length=512),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    for column in ("link", "source_url", "image_url"):
        op.alter_column(
            "google_news_articles",
            column,
            existing_type=sa.String(length=512),
            type_=sa.Text(),
            existing_nullable=True if column == "image_url" else False,
        )

    op.add_column(
        "google_news_articles",
        sa.Column("original_link", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "google_news_articles",
        sa.Column("content_fetched", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # `ceid` puede traer varios pares (feed dual ES/EN)
    op.alter_column(
        "google_news_config",
        "ceid",
        existing_type=sa.String(length=50),
        type_=sa.String(length=120),
        existing_nullable=False,
    )
    op.add_column(
        "google_news_config",
        sa.Column("days_window", sa.Integer(), nullable=False, server_default="1"),
    )

    # ── GitHub: campos usados por las cards y el detalle ──
    op.add_column(
        "github_repos",
        sa.Column("watchers_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("github_repos", sa.Column("homepage", sa.String(length=512), nullable=True))
    op.add_column(
        "github_repos",
        sa.Column("size_kb", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "github_repos",
        sa.Column("default_branch", sa.String(length=255), nullable=False, server_default="main"),
    )

    # ── Indices de los ORDER BY del feed ──
    op.create_index("ix_google_news_articles_pub_date", "google_news_articles", ["pub_date"])
    op.create_index("ix_google_news_articles_language", "google_news_articles", ["language"])
    op.create_index("ix_google_news_articles_fetched_at", "google_news_articles", ["fetched_at"])

    op.create_index("ix_github_repos_updated_at", "github_repos", ["updated_at"])
    op.create_index("ix_github_repos_stargazers", "github_repos", ["stargazers_count"])
    op.create_index("ix_github_repos_synced_at", "github_repos", ["synced_at"])

    op.create_index("ix_youtube_videos_published_at", "youtube_videos", ["published_at"])


def downgrade() -> None:
    op.drop_index("ix_youtube_videos_published_at", table_name="youtube_videos")

    op.drop_index("ix_github_repos_synced_at", table_name="github_repos")
    op.drop_index("ix_github_repos_stargazers", table_name="github_repos")
    op.drop_index("ix_github_repos_updated_at", table_name="github_repos")

    op.drop_index("ix_google_news_articles_fetched_at", table_name="google_news_articles")
    op.drop_index("ix_google_news_articles_language", table_name="google_news_articles")
    op.drop_index("ix_google_news_articles_pub_date", table_name="google_news_articles")

    op.drop_column("github_repos", "default_branch")
    op.drop_column("github_repos", "size_kb")
    op.drop_column("github_repos", "homepage")
    op.drop_column("github_repos", "watchers_count")

    op.drop_column("google_news_config", "days_window")
    op.alter_column(
        "google_news_config",
        "ceid",
        existing_type=sa.String(length=120),
        type_=sa.String(length=50),
        existing_nullable=False,
    )

    op.drop_column("google_news_articles", "content_fetched")
    op.drop_column("google_news_articles", "original_link")

    for column in ("link", "source_url", "image_url"):
        op.alter_column(
            "google_news_articles",
            column,
            existing_type=sa.Text(),
            type_=sa.String(length=512),
            existing_nullable=True if column == "image_url" else False,
        )
    op.alter_column(
        "google_news_articles",
        "id",
        existing_type=sa.String(length=64),
        type_=sa.String(length=512),
        existing_nullable=False,
    )