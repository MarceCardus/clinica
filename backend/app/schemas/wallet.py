from datetime import datetime
from decimal import Decimal
from typing import List

from pydantic import BaseModel

from app.models.topup import TopUpStatus
from app.models.wallet import LedgerType
from app.models.withdrawal import WithdrawalStatus


class WalletEntry(BaseModel):
    id: int
    type: LedgerType
    amount: Decimal
    balance_after: Decimal
    ref_table: str | None
    ref_id: int | None
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class BalanceResponse(BaseModel):
    balance: Decimal


class TopUpCreate(BaseModel):
    amount: Decimal
    bank_name: str
    ref_number: str


class TopUpRead(BaseModel):
    id: int
    amount: Decimal
    bank_name: str
    ref_number: str
    proof_url: str
    status: TopUpStatus
    reviewed_by: int | None
    reviewed_at: datetime | None
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class TopUpReview(BaseModel):
    status: TopUpStatus


class WithdrawalCreate(BaseModel):
    amount: Decimal
    bank_alias: str
    bank_holder: str


class WithdrawalRead(BaseModel):
    id: int
    amount: Decimal
    bank_alias: str
    bank_holder: str
    status: WithdrawalStatus
    processed_by: int | None
    processed_at: datetime | None
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class WithdrawalReview(BaseModel):
    status: WithdrawalStatus
