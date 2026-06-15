"""update_admin_user

Revision ID: 484fe2abc8a1
Revises: c2e38f8947b1
Create Date: 2026-01-09 11:14:48.865877

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy import String, Integer

# revision identifiers, used by Alembic.
revision = '484fe2abc8a1'
down_revision = 'c2e38f8947b1'
branch_labels = None
depends_on = None

def upgrade():
    # Define the table structure for the update
    kullanici_table = table('kullanici',
        column('kullanici_adi', String),
        column('rol', String),
        column('yetki_duzeyi', Integer),
        column('ad_soyad', String)
    )

    # Update the admin user
    op.execute(
        kullanici_table.update().where(
            kullanici_table.c.kullanici_adi == 'admin'
        ).values(
            rol='admin',
            yetki_duzeyi=3,
            ad_soyad='Sistem Yöneticisi'
        )
    )

def downgrade():
    # Revert changes if necessary (optional for data migrations)
    # Ideally we would store the previous state, but for a fix script,
    # we might just want to revert to a default state or do nothing.
    # Here we will do nothing as the previous state is unknown/undefined.
    pass
