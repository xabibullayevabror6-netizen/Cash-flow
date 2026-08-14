"""add provodka category source

Kategoriya endi Кор. счет provodkasidan ham aniqlanadi, shuning uchun
categorysource enum'iga yangi qiymat qo'shiladi.

Eslatma: enum qiymatini qo'shishni Alembic autogenerate aniqlamaydi —
bu migratsiya qo'lda yozilgan.

Revision ID: c92f1a5d7e30
Revises: b861aa48319a
Create Date: 2026-08-13
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c92f1a5d7e30"
down_revision: Union[str, None] = "b861aa48319a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF NOT EXISTS — migratsiya takroran ishlatilsa xato bermasin
    op.execute("ALTER TYPE categorysource ADD VALUE IF NOT EXISTS 'provodka'")


def downgrade() -> None:
    # PostgreSQL enum qiymatini o'chirishga ruxsat bermaydi — butun turni
    # qayta yaratish kerak bo'lardi. Qiymat qolgani zarar keltirmaydi,
    # shuning uchun ataylab hech narsa qilinmaydi.
    pass
