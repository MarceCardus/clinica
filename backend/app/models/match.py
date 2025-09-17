from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, SmallInteger
from sqlalchemy.orm import relationship

from app.models.base import Base


class MatchState(str, Enum):  # type: ignore[misc]
    SCHEDULED = "SCHEDULED"
    LIVE = "LIVE"
    FINISHED = "FINISHED"


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    state = Column(Enum(MatchState), nullable=False, default=MatchState.SCHEDULED)
    home_score = Column(SmallInteger, default=0)
    away_score = Column(SmallInteger, default=0)
    locked_bool = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    tournament = relationship("Tournament", backref="matches")
    home_team = relationship("Team", foreign_keys=[home_team_id])
    away_team = relationship("Team", foreign_keys=[away_team_id])
