"""rename power column name

Revision ID: 0ab78960d787
Revises: 9edca37270a3
Create Date: 2022-11-16 16:15:05.027745

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0ab78960d787'
down_revision = '9edca37270a3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('power_algo_system', sa.Column('on', sa.Boolean(), nullable=True))
    op.drop_column('power_algo_system', 'power')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('power_algo_system', sa.Column('power', sa.BOOLEAN(), autoincrement=False, nullable=True))
    op.drop_column('power_algo_system', 'on')
    # ### end Alembic commands ###
