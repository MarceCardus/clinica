from datetime import datetime

from sqlalchemy import Column, DateTime, DECIMAL, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import Base


class LedgerType(str, Enum):  # type: ignore[misc]
    TOPUP = "TOPUP"
    BET = "BET"
    BET_WIN = "BET_WIN"
    WITHDRAWAL = "WITHDRAWAL"
    ADJUST = "ADJUST"


class WalletLedger(Base):
    __tablename__ = "wallet_ledger"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(Enum(LedgerType), nullable=False)
    amount = Column(DECIMAL(18, 2), nullable=False)
    balance_after = Column(DECIMAL(18, 2), nullable=False)
    ref_table = Column(String(50), nullable=True)
    ref_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", backref="ledger_entries")
