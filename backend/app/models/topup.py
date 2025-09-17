from datetime import datetime

from sqlalchemy import Column, DateTime, DECIMAL, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import Base


class TopUpStatus(str, Enum):  # type: ignore[misc]
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class TopUp(Base):
    __tablename__ = "topups"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(DECIMAL(18, 2), nullable=False)
    bank_name = Column(String(255), nullable=False)
    ref_number = Column(String(255), nullable=False)
    proof_url = Column(String(255), nullable=False)
    status = Column(Enum(TopUpStatus), nullable=False, default=TopUpStatus.PENDING)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    unique_hash = Column(String(64), unique=True, nullable=False)

    user = relationship("User", foreign_keys=[user_id], backref="topups")
    reviewer = relationship("User", foreign_keys=[reviewed_by])
