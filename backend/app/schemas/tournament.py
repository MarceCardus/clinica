from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.match import MatchState
from app.models.market import MarketStatus, MarketType, SelectionType
from app.models.tournament import TournamentStatus


class TournamentBase(BaseModel):
    name: str
    company_name: str
    starts_at: datetime
    ends_at: datetime


class TournamentCreate(TournamentBase):
    status: TournamentStatus = TournamentStatus.ACTIVE


class TournamentRead(TournamentBase):
    id: int
    status: TournamentStatus
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class TeamBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class TeamCreate(TeamBase):
    tournament_id: int


class TeamRead(TeamBase):
    id: int
    tournament_id: int

    model_config = {
        "from_attributes": True,
    }


class MatchBase(BaseModel):
    tournament_id: int
    home_team_id: int
    away_team_id: int
    scheduled_at: datetime


class MatchCreate(MatchBase):
    pass


class MatchRead(MatchBase):
    id: int
    state: MatchState
    home_score: int
    away_score: int
    locked_bool: bool

    model_config = {
        "from_attributes": True,
    }


class MatchUpdateScore(BaseModel):
    home_score: int
    away_score: int
    state: MatchState


class MarketBase(BaseModel):
    match_id: int
    type: MarketType
    line: Optional[float] = None


class MarketCreate(MarketBase):
    pass


class MarketRead(MarketBase):
    id: int
    status: MarketStatus

    model_config = {
        "from_attributes": True,
    }


class MarketUpdateStatus(BaseModel):
    status: MarketStatus


class OddCreate(BaseModel):
    market_id: int
    selection: SelectionType
    price: float


class OddRead(OddCreate):
    id: int

    model_config = {
        "from_attributes": True,
    }
