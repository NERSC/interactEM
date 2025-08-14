"""replace_email_with_username

Revision ID: d259ec167e13
Revises: ae4ed8e4c67b
Create Date: 2025-05-28 01:29:13.231730

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'd259ec167e13'
down_revision = '4fd674e69396'
branch_labels = None
depends_on = None


def upgrade():
    # Add username column as nullable first
    op.add_column('user', sa.Column('username', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True))
    
    # Copy data from email to username
    op.execute('UPDATE "user" SET username = email')
    
    # Now make username NOT NULL
    op.alter_column('user', 'username', nullable=False)
    
    # Drop email index and create username index
    op.drop_index('ix_user_email', table_name='user')
    op.create_index(op.f('ix_user_username'), 'user', ['username'], unique=True)
    
    # Drop email column
    op.drop_column('user', 'email')


def downgrade():
    # Add email column back
    op.add_column('user', sa.Column('email', sa.VARCHAR(length=255), autoincrement=False, nullable=True))

    # Copy username back to email
    op.execute('UPDATE "user" SET email = username')

    # Make email NOT NULL
    op.alter_column('user', 'email', nullable=False)

    # Drop username index and recreate email index
    op.drop_index(op.f('ix_user_username'), table_name='user')
    op.create_index('ix_user_email', 'user', ['email'], unique=True)

    # Drop username column
    op.drop_column('user', 'username')
