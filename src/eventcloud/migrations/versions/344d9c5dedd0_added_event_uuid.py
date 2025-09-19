"""added event uuid

Revision ID: 344d9c5dedd0
Revises: e17360e5d6a8
Create Date: 2025-09-19 22:04:11.382218

"""

from typing import Sequence
from typing import Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "344d9c5dedd0"
down_revision: Union[str, Sequence[str], None] = "e17360e5d6a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("DROP TABLE IF EXISTS _alembic_tmp_events")
    # 1) Add column as NULLABLE first (not PK yet)
    op.add_column("events", sa.Column("uuid", sa.String(), nullable=True, index=True))

    # 2) Backfill existing rows with UUIDs (SQLite-safe)
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT rowid FROM events WHERE uuid IS NULL")).fetchall()
    for (rowid,) in rows:
        conn.execute(
            sa.text("UPDATE events SET uuid = :uuid WHERE rowid = :rowid"),
            {"uuid": str(uuid4()), "rowid": rowid},
        )

    # 3) Enforce NOT NULL and switch PK to uuid.
    # On SQLite this uses table recreation under the hood.
    with op.batch_alter_table("events", recreate="always") as batch:
        # Make uuid not nullable
        batch.alter_column("uuid", existing_type=sa.String(), nullable=False)
        # If `code` used to be the PK, switch PK to uuid
        # (drop/create PK is handled by recreation; just create a new PK explicitly)
        batch.create_primary_key("pk_events", ["uuid"])
        batch.drop_index("ix_events_code")
        # (optional) keep code unique or indexed if you still need fast lookups
        batch.create_index("ix_events_code", ["code"], unique=True)

    # If you have FKs pointing to events.code, update them in separate migrations
    # before/after this one to point to events.uuid instead.


def downgrade():
    # Revert PK to code (best-effort; adjust to your previous schema)
    with op.batch_alter_table("events", recreate="always") as batch:
        batch.drop_constraint("pk_events", type_="primary")
        batch.create_primary_key("pk_events", ["code"])
        batch.drop_index("ix_events_code")
    # allow uuid to be nullable again (or drop it if you want)
    with op.batch_alter_table("events", recreate="always") as batch:
        batch.alter_column("uuid", existing_type=sa.String(), nullable=True)
    op.drop_column("events", "uuid")
