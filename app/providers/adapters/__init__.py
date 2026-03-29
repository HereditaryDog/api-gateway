"""
Provider 专用适配器
"""

from app.providers.adapters.coding_plan import CodingPlanAdapter, CodingPlanAdapterWithFailover

__all__ = [
    "CodingPlanAdapter",
    "CodingPlanAdapterWithFailover",
]
