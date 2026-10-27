"""SQLAlchemy 資料模型。既有驗證資料表保留，新增車輛、車證申請與審核紀錄。"""
from datetime import datetime
from sqlalchemy import DDL, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Index, event
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base
from .security import utcnow

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_type: Mapped[str] = mapped_column(String(10))
    school_id: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(50))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    phone_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(10), default="applicant")
    status: Mapped[str] = mapped_column(String(10), default="pending")
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

class UserSession(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(40), index=True)
    target_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result: Mapped[str] = mapped_column(String(10), default="success")
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(200), nullable=True)
    detail: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (UniqueConstraint("license_plate", name="uq_vehicles_license_plate"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    license_plate: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    vehicle_type: Mapped[str] = mapped_column(String(20), nullable=False)
    make_model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    color: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

class PermitApplication(Base):
    __tablename__ = "permit_applications"
    __table_args__ = (Index("ix_permit_vehicle_status", "vehicle_id", "status"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    applicant_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="RESTRICT"), index=True)
    purpose: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True) # pending/approved/rejected/cancelled/expired
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

class PermitReview(Base):
    __tablename__ = "permit_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("permit_applications.id", ondelete="RESTRICT"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    decision: Mapped[str] = mapped_column(String(10), nullable=False) # approved/rejected
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

# 稽核日誌只允許新增。此保護不取代檔案權限、備份與外部日誌。
for _name, _op in (("audit_logs_no_update", "UPDATE"), ("audit_logs_no_delete", "DELETE")):
    event.listen(AuditLog.__table__, "after_create", DDL(
        f"CREATE TRIGGER IF NOT EXISTS {_name} BEFORE {_op} ON audit_logs "
        "BEGIN SELECT RAISE(ABORT, 'audit_logs is append-only'); END;"
    ))
