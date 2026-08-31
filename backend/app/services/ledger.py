from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.wallet import LedgerType, WalletLedger


def get_balance(db: Session, user_id: int) -> Decimal:
    total = db.scalar(select(func.coalesce(func.sum(WalletLedger.amount), 0)).where(WalletLedger.user_id == user_id))
    if total is None:
        return Decimal("0")
    return Decimal(str(total))


def add_entry(
    db: Session,
    *,
    user_id: int,
    entry_type: LedgerType,
    amount: Decimal,
    ref_table: Optional[str] = None,
    ref_id: Optional[int] = None,
) -> WalletLedger:
    current_balance = get_balance(db, user_id)
    new_balance = current_balance + amount
    entry = WalletLedger(
        user_id=user_id,
        type=entry_type,
        amount=amount,
        balance_after=new_balance,
        ref_table=ref_table,
        ref_id=ref_id,
    )
    db.add(entry)
    db.flush()
    return entry
