from datetime import datetime

from sqlalchemy import Column, DateTime, DECIMAL, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import Base


class MarketType(str, Enum):  # type: ignore[misc]
    ONE_X_TWO = "1X2"
    OVER_UNDER = "OVER_UNDER"


class MarketStatus(str, Enum):  # type: ignore[misc]
    OPEN = "OPEN"
    LOCKED = "LOCKED"
    SETTLED = "SETTLED"


class Market(Base):
    __tablename__ = "markets"

    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    type = Column(Enum(MarketType), nullable=False)
    line = Column(DECIMAL(4, 1), nullable=True)
    status = Column(Enum(MarketStatus), nullable=False, default=MarketStatus.OPEN)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    match = relationship("Match", backref="markets")


class SelectionType(str, Enum):  # type: ignore[misc]
    HOME = "HOME"
    DRAW = "DRAW"
    AWAY = "AWAY"
    OVER = "OVER"
    UNDER = "UNDER"


class Odd(Base):
    __tablename__ = "odds"

    id = Column(Integer, primary_key=True)
    market_id = Column(Integer, ForeignKey("markets.id"), nullable=False)
    selection = Column(Enum(SelectionType), nullable=False)
    price = Column(DECIMAL(6, 3), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    market = relationship("Market", backref="odds")
