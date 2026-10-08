"""add days_back to youtube config

Motivo: la ventana de antiguedad de YouTube estaba fija en el codigo
(`DAYS_BACK = 2` en `infrastructure/external/youtube_api.py`), sin forma de
cambiarla sin tocar el fuente. Se mueve a la config para poder ajustarla desde
la pantalla de Configuracion, igual que `days_window` en Google News y
`days_active` en GitHub.

- Anade `youtube_config.days_back` (INTEGER, NOT NULL, default 2), que es el
  valor que venian usando los DEFAULT y el clamp del backend, asi que las
  instalaciones existentes mantienen su comportamiento.

Es no destructiva: solo ensancha la tabla.

Revision ID: c3f8a1d92e47
Revises: b7e21c4a9f13
Create Date: 2026-10-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3f8a1d92e47"
down_revision: Union[str, Sequence[str], None] = "b7e21c4a9f13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "youtube_config",
        sa.Column(
            "days_back",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("2"),
        ),
    )


def downgrade() -> None:
    op.drop_column("youtube_config", "days_back")