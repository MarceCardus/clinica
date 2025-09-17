from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.bet import BetStatus
from app.models.market import SelectionType


class BetCreate(BaseModel):
    market_id: int
    selection: SelectionType
    stake: Decimal


class BetRead(BaseModel):
    id: int
    market_id: int
    selection: SelectionType
    stake: Decimal
    price_at_bet: Decimal
    potential_return: Decimal
    status: BetStatus
    placed_at: datetime
    settled_at: datetime | None

    model_config = {
        "from_attributes": True,
    }
