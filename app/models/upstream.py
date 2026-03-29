from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, Enum, JSON
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class ProviderType(str, enum.Enum):
    """支持的提供商类型"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"
    AZURE = "azure"
    CUSTOM = "custom"


class UpstreamProvider(Base):
    """上游提供商配置"""
    __tablename__ = "upstream_providers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    provider_type = Column(Enum(ProviderType), nullable=False)
    
    # API 基础 URL
    base_url = Column(String(255), nullable=False)
    
    # 默认模型映射 (json格式: {"gpt-3.5-turbo": "gpt-3.5-turbo", ...})
    model_mapping = Column(JSON, default={})
    
    # 状态
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=100)  # 优先级，数字越小优先级越高
    
    # 元数据
    remark = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class UpstreamKey(Base):
    """上游 API Key 表"""
    __tablename__ = "upstream_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, nullable=False, index=True)
    
    # API Key (加密存储)
    encrypted_key = Column(Text, nullable=False)
    
    # 状态
    is_active = Column(Boolean, default=True)
    is_exhausted = Column(Boolean, default=False)  # 是否已用完配额
    
    # 使用量统计
    total_requests = Column(Integer, default=0)
    total_tokens = Column(Float, default=0.0)
    
    # 优先级和权重 (负载均衡用)
    priority = Column(Integer, default=100)
    weight = Column(Integer, default=100)
    
    # 速率限制
    rpm_limit = Column(Integer, default=60)  # requests per minute
    tpm_limit = Column(Integer, default=100000)  # tokens per minute
    
    # 元数据
    remark = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_used_at = Column(DateTime(timezone=True))
    
    @property
    def health_score(self) -> float:
        """健康度评分 (0-100)"""
        if not self.is_active or self.is_exhausted:
            return 0.0
        # 根据使用量计算健康度
        usage_ratio = min(1.0, self.total_requests / 10000)
        return max(0, 100 - usage_ratio * 50)
