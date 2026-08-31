from datetime import datetime

from sqlalchemy import Column, DateTime, DECIMAL, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import Base


class WithdrawalStatus(str, Enum):  # type: ignore[misc]
    REQUESTED = "REQUESTED"
    PAID = "PAID"
    REJECTED = "REJECTED"


class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(DECIMAL(18, 2), nullable=False)
    bank_alias = Column(String(255), nullable=False)
    bank_holder = Column(String(255), nullable=False)
    status = Column(Enum(WithdrawalStatus), nullable=False, default=WithdrawalStatus.REQUESTED)
    processed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", foreign_keys=[user_id], backref="withdrawals")
    processor = relationship("User", foreign_keys=[processed_by])
