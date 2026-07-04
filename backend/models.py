from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Text,
    DateTime,
    Date,
    JSON,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

ROLES = ("admin", "worker", "store_keeper")
BIN_TYPES = ("OK", "REJECTED", "DOUBTFUL")
BIN_STATUSES = ("PENDING", "INWARDED", "RETURNED", "SCRAPPED", "UNDER_REVIEW")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(Text, nullable=False)
    role = Column(String(20), default="worker")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True, index=True)
    supplier_name = Column(String(200), unique=True, nullable=False)
    contact_info = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    part_number = Column(String(100), unique=True, nullable=False, index=True)
    part_name = Column(String(200), nullable=False)
    group_name = Column(String(200))
    parameters = Column(JSON, default=list)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class InspectionLog(Base):
    __tablename__ = "inspection_logs"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    part_name = Column(String(200))
    part_number = Column(String(100))
    stage = Column(String(100))
    supplier = Column(String(200))
    invoice_number = Column(String(200))
    lot_quantity = Column(Integer)
    checking_frequency = Column(Integer)
    measured_values = Column(JSON)
    status = Column(String(20))
    worker_remark = Column(Text)
    ai_category = Column(String(200))
    ai_report = Column(Text)
    logged_by = Column(String(100), ForeignKey("users.username"))
    iqc_lot = relationship("IqcLot", back_populates="inspection_log", uselist=False)


class IqcLot(Base):
    """Finalized IQC lot — one row per completed inspection log."""
    __tablename__ = "iqc_lots"
    id = Column(Integer, primary_key=True, index=True)
    inspection_log_id = Column(
        Integer, ForeignKey("inspection_logs.id"), unique=True, nullable=False
    )
    part_no = Column(String(100), nullable=False, index=True)
    supplier = Column(String(200), nullable=False)
    lot_quantity = Column(Integer, nullable=False, default=0)
    invoice_number = Column(String(200))
    lot_date = Column(DateTime(timezone=True), server_default=func.now())
    overall_status = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    inspection_log = relationship("InspectionLog", back_populates="iqc_lot")
    bin_items = relationship("StoreBinItem", back_populates="iqc_lot")


class StoreBinItem(Base):
    __tablename__ = "store_bin_items"
    id = Column(Integer, primary_key=True, index=True)
    iqc_lot_id = Column(Integer, ForeignKey("iqc_lots.id"), nullable=False, index=True)
    bin_type = Column(String(20), nullable=False, index=True)
    part_no = Column(String(100), nullable=False, index=True)
    supplier = Column(String(200), nullable=False)
    quantity = Column(Integer, nullable=False, default=0)
    lot_date = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(20), nullable=False, default="PENDING", index=True)
    grn_id = Column(Integer, ForeignKey("grn.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    iqc_lot = relationship("IqcLot", back_populates="bin_items")
    grn = relationship("Grn", foreign_keys=[grn_id], uselist=False)


class Grn(Base):
    __tablename__ = "grn"
    id = Column(Integer, primary_key=True, index=True)
    grn_no = Column(String(30), unique=True, nullable=False, index=True)
    store_bin_item_id = Column(
        Integer, ForeignKey("store_bin_items.id"), unique=True, nullable=False
    )
    part_no = Column(String(100), nullable=False, index=True)
    supplier = Column(String(200), nullable=False)
    quantity = Column(Integer, nullable=False)
    invoice_no = Column(String(200), nullable=False)
    invoice_date = Column(Date, nullable=False)
    store_keeper_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    store_bin_item = relationship(
        "StoreBinItem", foreign_keys=[store_bin_item_id], uselist=False
    )
    material_issues = relationship("MaterialIssue", back_populates="grn")


class MaterialIssue(Base):
    __tablename__ = "material_issues"
    id = Column(Integer, primary_key=True, index=True)
    issue_no = Column(String(30), unique=True, nullable=False, index=True)
    grn_id = Column(Integer, ForeignKey("grn.id"), nullable=False, index=True)
    part_no = Column(String(100), nullable=False, index=True)
    quantity_issued = Column(Integer, nullable=False)
    issued_to = Column(String(200), nullable=False)
    remarks = Column(Text)
    issued_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    grn = relationship("Grn", back_populates="material_issues")


class DocumentSequence(Base):
    """Race-safe sequential numbers for GRN / material issue documents."""
    __tablename__ = "document_sequences"
    id = Column(Integer, primary_key=True, index=True)
    doc_type = Column(String(20), nullable=False)
    year = Column(Integer, nullable=False)
    last_number = Column(Integer, nullable=False, default=0)

    __table_args__ = (UniqueConstraint("doc_type", "year", name="uq_doc_seq_type_year"),)
