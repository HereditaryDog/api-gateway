"""
上游 Provider 和 Key 模型
"""
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, Enum, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class ProviderType(str, enum.Enum):
    """支持的提供商类型"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"
    AZURE = "azure"
    SILICONFLOW = "siliconflow"
    MOONSHOT = "moonshot"
    ZHIPU = "zhipu"
    ALIBABA = "alibaba"
    BAIDU = "baidu"
    CUSTOM = "custom"


class UpstreamProvider(Base):
    """上游提供商配置"""
    __tablename__ = "upstream_providers"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    provider_type = Column(Enum(ProviderType), nullable=False)
    
    # API 基础 URL
    base_url = Column(String(255), nullable=False)
    
    # 默认模型映射 (json格式)
    model_mapping = Column(JSON, default=dict, nullable=False)
    
    # 状态
    is_active = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=100, nullable=False)  # 优先级，数字越小优先级越高
    
    # 元数据
    remark = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)


class UpstreamKey(Base):
    """上游 API Key 表"""
    __tablename__ = "upstream_keys"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    provider_id = Column(Integer, nullable=False, index=True)
    
    # API Key (加密存储)
    encrypted_key = Column(Text, nullable=False)
    
    # 状态
    is_active = Column(Boolean, default=True, nullable=False)
    is_exhausted = Column(Boolean, default=False, nullable=False)  # 是否已用完配额
    
    # 使用量统计
    total_requests = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Float, default=0.0, nullable=False)
    
    # 优先级和权重 (负载均衡用)
    priority = Column(Integer, default=100, nullable=False)
    weight = Column(Integer, default=100, nullable=False)
    
    # 速率限制
    rpm_limit = Column(Integer, default=60, nullable=False)  # requests per minute
    tpm_limit = Column(Integer, default=100000, nullable=False)  # tokens per minute
    
    # 元数据
    remark = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    @property
    def health_score(self) -> float:
        """健康度评分 (0-100)"""
        if not self.is_active or self.is_exhausted:
            return 0.0
        # 根据使用量计算健康度
        usage_ratio = min(1.0, self.total_requests / 10000)
        return max(0.0, 100.0 - usage_ratio * 50)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "provider_id": self.provider_id,
            "encrypted_key": self.encrypted_key,
            "is_active": bool(self.is_active) if self.is_active is not None else True,
            "is_exhausted": bool(self.is_exhausted) if self.is_exhausted is not None else False,
            "total_requests": int(self.total_requests or 0),
            "total_tokens": float(self.total_tokens or 0),
            "priority": int(self.priority or 100),
            "weight": int(self.weight or 100),
            "rpm_limit": int(self.rpm_limit or 60),
            "tpm_limit": int(self.tpm_limit or 100000),
            "health_score": self.health_score,
            "remark": self.remark,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }
