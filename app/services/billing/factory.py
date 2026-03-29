"""
计费策略工厂
根据 Provider 配置自动选择计费策略
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.billing.base import BillingStrategy
from app.services.billing.token_based import TokenBasedBillingStrategy
from app.services.billing.request_based import RequestBasedBillingStrategy
from app.models.billing import ProviderBillingConfig, BillingMode
from app.models.upstream import UpstreamProvider


class BillingStrategyFactory:
    """计费策略工厂"""
    
    @staticmethod
    async def create_strategy(
        db: AsyncSession,
        provider_id: Optional[int] = None,
        provider_type: Optional[str] = None,
        model: Optional[str] = None
    ) -> BillingStrategy:
        """
        创建计费策略
        
        策略选择逻辑:
        1. 如果有 provider_id，查询其计费配置
        2. 根据 billing_mode 选择策略
        3. 默认使用 Token 计费
        
        Args:
            db: 数据库会话
            provider_id: 上游 Provider ID
            provider_type: Provider 类型（如 'openai', 'coding_plan'）
            model: 模型名称
        
        Returns:
            计费策略实例
        """
        # 如果有 provider_id，查询计费配置
        if provider_id:
            result = await db.execute(
                select(ProviderBillingConfig).where(
                    ProviderBillingConfig.provider_id == provider_id
                )
            )
            config = result.scalar_one_or_none()
            
            if config:
                if config.billing_mode == BillingMode.REQUEST:
                    return RequestBasedBillingStrategy(db, provider_id)
                elif config.billing_mode == BillingMode.TOKEN:
                    return TokenBasedBillingStrategy(db)
        
        # 根据 provider_type 判断
        if provider_type:
            # Coding Plan 类型使用请求计费
            if "coding" in provider_type.lower() or "bailian" in provider_type.lower():
                # 尝试找到对应的 provider_id
                if not provider_id:
                    result = await db.execute(
                        select(UpstreamProvider).where(
                            UpstreamProvider.provider_type == provider_type
                        )
                    )
                    provider = result.scalar_one_or_none()
                    if provider:
                        provider_id = provider.id
                
                return RequestBasedBillingStrategy(db, provider_id)
        
        # 默认使用 Token 计费
        return TokenBasedBillingStrategy(db)
    
    @staticmethod
    async def get_strategy_for_model(
        db: AsyncSession,
        model: str
    ) -> tuple[BillingStrategy, Optional[int]]:
        """
        根据模型名称获取计费策略
        
        Args:
            db: 数据库会话
            model: 模型名称（如 'openai/gpt-4', 'coding-plan/gpt-4'）
        
        Returns:
            (计费策略, provider_id)
        """
        # 解析 provider 前缀
        provider_type = None
        if '/' in model:
            provider_type = model.split('/', 1)[0]
        
        # 查找对应的 provider
        provider_id = None
        if provider_type:
            # 先尝试通过 model_mapping 查找
            result = await db.execute(select(UpstreamProvider))
            providers = result.scalars().all()
            
            for provider in providers:
                if provider.model_mapping:
                    for mapped_model in provider.model_mapping.keys():
                        if mapped_model in model or model in mapped_model:
                            provider_id = provider.id
                            provider_type = provider.provider_type.value if provider.provider_type else provider_type
                            break
                if provider_id:
                    break
            
            # 如果没找到，尝试通过 provider_type 查找
            if not provider_id:
                result = await db.execute(
                    select(UpstreamProvider).where(
                        UpstreamProvider.provider_type == provider_type
                    )
                )
                provider = result.scalar_one_or_none()
                if provider:
                    provider_id = provider.id
        
        strategy = await BillingStrategyFactory.create_strategy(
            db, provider_id, provider_type, model
        )
        
        return strategy, provider_id
    
    @staticmethod
    def create_token_strategy(db: AsyncSession) -> TokenBasedBillingStrategy:
        """创建 Token 计费策略（快捷方法）"""
        return TokenBasedBillingStrategy(db)
    
    @staticmethod
    def create_request_strategy(
        db: AsyncSession,
        provider_id: Optional[int] = None
    ) -> RequestBasedBillingStrategy:
        """创建请求计费策略（快捷方法）"""
        return RequestBasedBillingStrategy(db, provider_id)
