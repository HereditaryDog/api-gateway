from app.providers.adapters.coding_plan.base import CodingPlanBaseAdapter
from app.providers.transformers import CodingPlanVolcengineTransformer


class VolcengineCodingPlanAdapter(CodingPlanBaseAdapter):
    def __init__(self, *, db, provider_record, transport=None):
        super().__init__(
            db=db,
            provider_record=provider_record,
            transformer=CodingPlanVolcengineTransformer(),
            transport=transport,
        )
