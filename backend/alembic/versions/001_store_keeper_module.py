"""Add store keeper module tables (additive migration).

Revision ID: 001_store_keeper
Revises:
Create Date: 2026-07-05
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_store_keeper"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "iqc_lots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("inspection_log_id", sa.Integer(), nullable=False),
        sa.Column("part_no", sa.String(length=100), nullable=False),
        sa.Column("supplier", sa.String(length=200), nullable=False),
        sa.Column("lot_quantity", sa.Integer(), nullable=False),
        sa.Column("invoice_number", sa.String(length=200), nullable=True),
        sa.Column("lot_date", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("overall_status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["inspection_log_id"], ["inspection_logs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inspection_log_id"),
    )
    op.create_index("ix_iqc_lots_part_no", "iqc_lots", ["part_no"])

    op.create_table(
        "document_sequences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("doc_type", sa.String(length=20), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_type", "year", name="uq_doc_seq_type_year"),
    )

    op.create_table(
        "store_bin_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("iqc_lot_id", sa.Integer(), nullable=False),
        sa.Column("bin_type", sa.String(length=20), nullable=False),
        sa.Column("part_no", sa.String(length=100), nullable=False),
        sa.Column("supplier", sa.String(length=200), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("lot_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("grn_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["iqc_lot_id"], ["iqc_lots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_store_bin_items_bin_type", "store_bin_items", ["bin_type"])
    op.create_index("ix_store_bin_items_part_no", "store_bin_items", ["part_no"])

    op.create_table(
        "grn",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("grn_no", sa.String(length=30), nullable=False),
        sa.Column("store_bin_item_id", sa.Integer(), nullable=False),
        sa.Column("part_no", sa.String(length=100), nullable=False),
        sa.Column("supplier", sa.String(length=200), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("invoice_no", sa.String(length=200), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("store_keeper_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["store_bin_item_id"], ["store_bin_items.id"]),
        sa.ForeignKeyConstraint(["store_keeper_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("grn_no"),
        sa.UniqueConstraint("store_bin_item_id"),
    )
    op.create_index("ix_grn_grn_no", "grn", ["grn_no"])
    op.create_index("ix_grn_part_no", "grn", ["part_no"])

    op.create_foreign_key(
        "fk_store_bin_items_grn_id",
        "store_bin_items",
        "grn",
        ["grn_id"],
        ["id"],
    )

    op.create_table(
        "material_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("issue_no", sa.String(length=30), nullable=False),
        sa.Column("grn_id", sa.Integer(), nullable=False),
        sa.Column("part_no", sa.String(length=100), nullable=False),
        sa.Column("quantity_issued", sa.Integer(), nullable=False),
        sa.Column("issued_to", sa.String(length=200), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("issued_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["grn_id"], ["grn.id"]),
        sa.ForeignKeyConstraint(["issued_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("issue_no"),
    )
    op.create_index("ix_material_issues_grn_id", "material_issues", ["grn_id"])


def downgrade() -> None:
    op.drop_table("material_issues")
    op.drop_constraint("fk_store_bin_items_grn_id", "store_bin_items", type_="foreignkey")
    op.drop_table("grn")
    op.drop_table("store_bin_items")
    op.drop_table("document_sequences")
    op.drop_table("iqc_lots")
