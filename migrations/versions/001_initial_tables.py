"""Initial tables creation

Revision ID: 001_initial_tables
Revises: 
Create Date: 2025-08-26 20:19:49.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_initial_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(50), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    # Create currencies table
    op.create_table('currencies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('symbol', sa.String(10), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False),
        sa.Column('bind_curr_ticker', sa.String(10), nullable=False),
        sa.Column('cmc_rank', sa.Integer(), nullable=True),
        sa.Column('circulating_supply', sa.Float(), nullable=True),
        sa.Column('total_supply', sa.Float(), nullable=True),
        sa.Column('max_supply', sa.Float(), nullable=True),
        sa.Column('infinite_supply', sa.Boolean(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.Column('date_added', sa.DateTime(), nullable=False),
        sa.Column('tags', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_currencies_id'), 'currencies', ['id'], unique=False)
    op.create_index(op.f('ix_currencies_name'), 'currencies', ['name'], unique=False)
    op.create_index(op.f('ix_currencies_symbol'), 'currencies', ['symbol'], unique=False)
    op.create_index(op.f('ix_currencies_slug'), 'currencies', ['slug'], unique=False)
    op.create_index(op.f('ix_currencies_bind_curr_ticker'), 'currencies', ['bind_curr_ticker'], unique=False)

    # Create settings table
    op.create_table('settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('value', sa.String(500), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_settings_id'), 'settings', ['id'], unique=False)
    op.create_index(op.f('ix_settings_name'), 'settings', ['name'], unique=True)

    # Create rates table
    op.create_table('rates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('custom_curr', sa.Integer(), nullable=False),
        sa.Column('bind_curr', sa.String(10), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('volume_24h', sa.Float(), nullable=True),
        sa.Column('volume_change_24h', sa.Float(), nullable=True),
        sa.Column('percent_change_1h', sa.Float(), nullable=True),
        sa.Column('percent_change_24h', sa.Float(), nullable=True),
        sa.Column('percent_change_7d', sa.Float(), nullable=True),
        sa.Column('market_cap', sa.Float(), nullable=True),
        sa.Column('market_cap_dominance', sa.Float(), nullable=True),
        sa.Column('fully_diluted_market_cap', sa.Float(), nullable=True),
        sa.Column('date_created', sa.DateTime(), nullable=False),
        sa.Column('date_activation', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['custom_curr'], ['currencies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rates_id'), 'rates', ['id'], unique=False)
    op.create_index(op.f('ix_rates_custom_curr'), 'rates', ['custom_curr'], unique=False)
    op.create_index(op.f('ix_rates_bind_curr'), 'rates', ['bind_curr'], unique=False)
    op.create_index(op.f('ix_rates_date_activation'), 'rates', ['date_activation'], unique=False)

    # Insert default settings
    settings_table = sa.table('settings',
        sa.column('name', sa.String),
        sa.column('value', sa.String),
        sa.column('active', sa.Boolean)
    )
    
    op.bulk_insert(settings_table,
        [
            {
                'name': 'caching_time',
                'value': '300',
                'active': True
            }
        ]
    )


def downgrade():
    op.drop_table('rates')
    op.drop_table('settings')
    op.drop_table('currencies')
    op.drop_table('users')
