from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import Base


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    name = Column(String(255), nullable=False)

    tournament = relationship("Tournament", backref="teams")
