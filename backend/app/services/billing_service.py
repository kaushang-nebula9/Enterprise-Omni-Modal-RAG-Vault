import logging
from datetime import datetime
from uuid import UUID
from sqlalchemy import and_
from sqlalchemy.orm import Session
from app.models.usage_log import UsageLog
from app.models.available_model import AvailableModel

logger = logging.getLogger(__name__)


def calculate_tenant_monthly_cost(db: Session, tenant_id: UUID) -> float:
    """
    Calculate the total estimated usage cost for a tenant during the current calendar month.
    Uses model-specific pricing from AvailableModel, and treats unconfigured pricing fields as 0.0.
    """
    now = datetime.utcnow()
    start_of_month = datetime(now.year, now.month, 1, 0, 0, 0)

    rows = (
        db.query(
            UsageLog.input_tokens,
            UsageLog.output_tokens,
            UsageLog.model_string,
            UsageLog.provider,
            AvailableModel.input_cost_per_million_tokens,
            AvailableModel.output_cost_per_million_tokens,
        )
        .outerjoin(
            AvailableModel,
            and_(
                UsageLog.model_string == AvailableModel.model_name,
                UsageLog.provider == AvailableModel.provider_id,
            ),
        )
        .filter(UsageLog.tenant_id == tenant_id, UsageLog.created_at >= start_of_month)
        .all()
    )

    total_cost = 0.0
    for (
        input_tokens,
        output_tokens,
        model_string,
        provider,
        input_price,
        output_price,
    ) in rows:
        # If input price is configured, calculate input cost, otherwise 0
        input_cost = (
            (input_tokens / 1_000_000.0 * float(input_price))
            if input_price is not None
            else 0.0
        )
        # If output price is configured, calculate output cost, otherwise 0
        output_cost = (
            (output_tokens / 1_000_000.0 * float(output_price))
            if output_price is not None
            else 0.0
        )

        if input_price is None or output_price is None:
            logger.warning(
                f"Pricing not fully configured for model='{model_string}', provider='{provider}'. "
                f"Treating unconfigured price as $0.00."
            )
        total_cost += input_cost + output_cost

    return round(total_cost, 4)
