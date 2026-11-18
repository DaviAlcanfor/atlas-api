"""chat_tool_logs (spec 038): one row per chat tool call (no user text, no IP), kept 14 days; additive

Revision ID: 0023
Revises: 0022
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_tool_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("tool", sa.Text(), nullable=False),
        sa.Column("args", JSONB(), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_chat_tool_logs_ts", "chat_tool_logs", ["ts"])


def downgrade() -> None:
    op.drop_table("chat_tool_logs")
