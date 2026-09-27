"""Initial database schema covering Backend.md §5

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-27 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from app.models.base import GUID

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Users table
    op.create_table(
        'users',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('location', sa.JSON(), nullable=True),
        sa.Column('units', sa.String(length=20), nullable=False, server_default='metric'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. User Preferences table
    op.create_table(
        'user_preferences',
        sa.Column('user_id', GUID(), nullable=False),
        sa.Column('style_tags', sa.JSON(), nullable=False),
        sa.Column('color_affinity', sa.JSON(), nullable=False),
        sa.Column('category_affinity', sa.JSON(), nullable=False),
        sa.Column('dress_code_overrides', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id')
    )

    # 3. Clothing Items table
    op.create_table(
        'clothing_items',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('user_id', GUID(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('subtype', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='processing'),
        sa.Column('wear_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_worn_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_clothing_items_user_id'), 'clothing_items', ['user_id'], unique=False)
    op.create_index(op.f('ix_clothing_items_category'), 'clothing_items', ['category'], unique=False)
    op.create_index(op.f('ix_clothing_items_status'), 'clothing_items', ['status'], unique=False)

    # 4. Clothing Images table
    op.create_table(
        'clothing_images',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('clothing_item_id', GUID(), nullable=False),
        sa.Column('original_url', sa.String(length=1024), nullable=False),
        sa.Column('enhanced_url', sa.String(length=1024), nullable=True),
        sa.Column('thumbnail_url', sa.String(length=1024), nullable=True),
        sa.Column('quality_band', sa.String(length=20), nullable=False, server_default='good'),
        sa.Column('enhancement_applied', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('quality_metrics', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['clothing_item_id'], ['clothing_items.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('clothing_item_id')
    )

    # 5. Clothing Attributes table
    op.create_table(
        'clothing_attributes',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('clothing_item_id', GUID(), nullable=False),
        sa.Column('color_primary', sa.String(length=50), nullable=True),
        sa.Column('color_secondary', sa.String(length=50), nullable=True),
        sa.Column('pattern', sa.String(length=50), nullable=True),
        sa.Column('pattern_confidence', sa.Float(), nullable=True),
        sa.Column('formality_estimate', sa.String(length=50), nullable=True),
        sa.Column('formality_confidence', sa.Float(), nullable=True),
        sa.Column('season_tags', sa.JSON(), nullable=False),
        sa.Column('embedding', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['clothing_item_id'], ['clothing_items.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('clothing_item_id')
    )
    op.create_index(op.f('ix_clothing_attributes_color_primary'), 'clothing_attributes', ['color_primary'], unique=False)

    # 6. Outfits table
    op.create_table(
        'outfits',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('user_id', GUID(), nullable=False),
        sa.Column('occasion', sa.String(length=50), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False, server_default='recommendation'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_outfits_user_id'), 'outfits', ['user_id'], unique=False)
    op.create_index(op.f('ix_outfits_occasion'), 'outfits', ['occasion'], unique=False)

    # 7. Outfit Items table
    op.create_table(
        'outfit_items',
        sa.Column('outfit_id', GUID(), nullable=False),
        sa.Column('clothing_item_id', GUID(), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='item'),
        sa.ForeignKeyConstraint(['clothing_item_id'], ['clothing_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['outfit_id'], ['outfits.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('outfit_id', 'clothing_item_id')
    )

    # 8. Weather Snapshots table
    op.create_table(
        'weather_snapshots',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('temperature', sa.Float(), nullable=False),
        sa.Column('feels_like', sa.Float(), nullable=False),
        sa.Column('humidity', sa.Float(), nullable=False),
        sa.Column('precipitation_prob', sa.Float(), nullable=False),
        sa.Column('wind_speed', sa.Float(), nullable=False),
        sa.Column('condition', sa.String(length=100), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # 9. Recommendations table
    op.create_table(
        'recommendations',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('outfit_id', GUID(), nullable=False),
        sa.Column('weather_snapshot_id', GUID(), nullable=True),
        sa.Column('weather_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('occasion_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('color_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('style_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('personalization_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('diversity_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('final_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['outfit_id'], ['outfits.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['weather_snapshot_id'], ['weather_snapshots.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # 10. Feedbacks table
    op.create_table(
        'feedbacks',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('user_id', GUID(), nullable=False),
        sa.Column('outfit_id', GUID(), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['outfit_id'], ['outfits.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('feedbacks')
    op.drop_table('recommendations')
    op.drop_table('weather_snapshots')
    op.drop_table('outfit_items')
    op.drop_table('outfits')
    op.drop_table('clothing_attributes')
    op.drop_table('clothing_images')
    op.drop_table('clothing_items')
    op.drop_table('user_preferences')
    op.drop_table('users')
