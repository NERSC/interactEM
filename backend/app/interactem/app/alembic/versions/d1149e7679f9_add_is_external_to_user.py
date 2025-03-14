"""Add is_external to User

Revision ID: d1149e7679f9
Revises: 516457e800b5
Create Date: 2025-01-15 15:09:21.905064

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'd1149e7679f9'
down_revision = '516457e800b5'
branch_labels = None
depends_on = None


def upgrade():
    # Add column with default value as false (not using autogenerated)
    op.add_column('user', sa.Column('is_external', sa.Boolean(), server_default="f", nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('user', 'is_external')
    # ### end Alembic commands ###
