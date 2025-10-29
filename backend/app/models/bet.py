from datetime import datetime

from sqlalchemy import Column, DateTime, DECIMAL, Enum, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.models.market import SelectionType


class BetStatus(str, Enum):  # type: ignore[misc]
    PLACED = "PLACED"
    WON = "WON"
    LOST = "LOST"
    VOID = "VOID"


class Bet(Base):
    __tablename__ = "bets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    market_id = Column(Integer, ForeignKey("markets.id"), nullable=False)
    selection = Column(Enum(SelectionType), nullable=False)
    stake = Column(DECIMAL(18, 2), nullable=False)
    price_at_bet = Column(DECIMAL(6, 3), nullable=False)
    potential_return = Column(DECIMAL(18, 2), nullable=False)
    status = Column(Enum(BetStatus), nullable=False, default=BetStatus.PLACED)
    placed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    settled_at = Column(DateTime, nullable=True)

    user = relationship("User", backref="bets")
    market = relationship("Market", backref="bets")
