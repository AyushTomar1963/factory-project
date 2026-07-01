from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"
    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(Text, nullable=False)
    role            = Column(String(20), default="worker")
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

class Supplier(Base):
    __tablename__ = "suppliers"
    id            = Column(Integer, primary_key=True, index=True)
    supplier_name = Column(String(200), unique=True, nullable=False)
    contact_info  = Column(Text)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

class Product(Base):
    __tablename__ = "products"
    id          = Column(Integer, primary_key=True, index=True)
    part_number = Column(String(100), unique=True, nullable=False, index=True)
    part_name   = Column(String(200), nullable=False)
    group_name  = Column(String(200))
    parameters  = Column(JSON, default=list)   # ["OD", "ID", "Length"]
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

class InspectionLog(Base):
    __tablename__ = "inspection_logs"
    id                 = Column(Integer, primary_key=True, index=True)
    timestamp          = Column(DateTime(timezone=True), server_default=func.now())
    part_name          = Column(String(200))
    part_number        = Column(String(100))
    stage              = Column(String(100))
    supplier           = Column(String(200))
    invoice_number     = Column(String(200))
    lot_quantity       = Column(Integer)
    checking_frequency = Column(Integer)
    measured_values    = Column(JSON)          # {"OD": "GREEN", "ID": "RED"}
    status             = Column(String(20))    # GREEN | YELLOW | RED
    worker_remark      = Column(Text)
    ai_category        = Column(String(200))
    ai_report          = Column(Text)
    logged_by          = Column(String(100), ForeignKey("users.username"))
