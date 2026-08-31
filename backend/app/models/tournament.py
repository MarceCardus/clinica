from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Integer, String

from app.models.base import Base


class TournamentStatus(str, Enum):  # type: ignore[misc]
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    FINISHED = "FINISHED"


class Tournament(Base):
    __tablename__ = "tournaments"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=False)
    starts_at = Column(DateTime, nullable=False)
    ends_at = Column(DateTime, nullable=False)
    status = Column(Enum(TournamentStatus), nullable=False, default=TournamentStatus.DRAFT)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
