"""
风控相关模型
"""
from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class SensitiveWord(Base):
    __tablename__ = "sensitive_words"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    term = Column(String(255), nullable=False, unique=True, index=True)
    scope = Column(String(50), nullable=False, default="completion")
    is_active = Column(Boolean, nullable=False, default=True)
    priority = Column(Integer, nullable=False, default=100)
    remark = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)


class SensitiveWordAuditLog(Base):
    __tablename__ = "sensitive_word_audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    path = Column(String(255), nullable=False, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    client_ip = Column(String(100), nullable=True)
    matched_word_ids = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
