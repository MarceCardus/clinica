from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db, require_role
from app.models.market import Market, MarketStatus, Odd
from app.models.match import Match, MatchState
from app.models.team import Team
from app.models.tournament import Tournament
from app.models.user import UserRole
from app.schemas.tournament import (
    MarketCreate,
    MarketRead,
    MarketUpdateStatus,
    MatchCreate,
    MatchRead,
    MatchUpdateScore,
    OddCreate,
    OddRead,
    TeamCreate,
    TeamRead,
    TournamentCreate,
    TournamentRead,
)
from app.services.audit import record_audit
from app.services.settlement import lock_markets, settle_match

router = APIRouter(prefix="/tournaments", tags=["torneos"])


@router.get("", response_model=list[TournamentRead])
def list_tournaments(db: Session = Depends(get_db)):
    return db.query(Tournament).order_by(Tournament.starts_at).all()


@router.post("", response_model=TournamentRead, status_code=status.HTTP_201_CREATED)
def create_tournament(
    payload: TournamentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN, UserRole.ORGANIZER)),
):
    tournament = Tournament(**payload.model_dump())
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    record_audit(
        db,
        user_id=current_user.id,
        action="TOURNAMENT_CREATE",
        entity="Tournament",
        entity_id=tournament.id,
        summary={"name": tournament.name},
    )
    return tournament


@router.post("/teams", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
def create_team(
    payload: TeamCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN, UserRole.ORGANIZER)),
):
    tournament = db.get(Tournament, payload.tournament_id)
    if not tournament:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")
    team = Team(**payload.model_dump())
    db.add(team)
    db.commit()
    db.refresh(team)
    record_audit(
        db,
        user_id=current_user.id,
        action="TEAM_CREATE",
        entity="Team",
        entity_id=team.id,
        summary={"name": team.name},
    )
    return team


@router.post("/matches", response_model=MatchRead, status_code=status.HTTP_201_CREATED)
def create_match(
    payload: MatchCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN, UserRole.ORGANIZER)),
):
    match = Match(**payload.model_dump())
    db.add(match)
    db.commit()
    db.refresh(match)
    record_audit(
        db,
        user_id=current_user.id,
        action="MATCH_CREATE",
        entity="Match",
        entity_id=match.id,
        summary={"tournament": match.tournament_id},
    )
    return match


@router.get("/{tournament_id}/matches", response_model=list[MatchRead])
def list_matches(tournament_id: int, db: Session = Depends(get_db)):
    matches = (
        db.query(Match)
        .filter(Match.tournament_id == tournament_id)
        .order_by(Match.scheduled_at)
        .all()
    )
    return matches


@router.patch("/matches/{match_id}/lock", response_model=MatchRead)
def lock_match(
    match_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN, UserRole.ORGANIZER)),
):
    match = (
        db.query(Match)
        .options(joinedload(Match.markets))
        .filter(Match.id == match_id)
        .first()
    )
    if not match:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    lock_markets(db, match)
    match.state = MatchState.LIVE
    db.commit()
    db.refresh(match)
    record_audit(
        db,
        user_id=current_user.id,
        action="MATCH_LOCK",
        entity="Match",
        entity_id=match.id,
        summary={"state": match.state.value},
    )
    return match


@router.patch("/matches/{match_id}/result", response_model=MatchRead)
def close_match(
    match_id: int,
    payload: MatchUpdateScore,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN, UserRole.ORGANIZER)),
):
    match = (
        db.query(Match)
        .options(joinedload(Match.markets).joinedload(Market.bets))
        .filter(Match.id == match_id)
        .first()
    )
    if not match:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    match.home_score = payload.home_score
    match.away_score = payload.away_score
    match.state = payload.state
    if payload.state == MatchState.LIVE:
        lock_markets(db, match)
    if payload.state == MatchState.FINISHED:
        settle_match(db, match)
    db.commit()
    db.refresh(match)
    record_audit(
        db,
        user_id=current_user.id,
        action="MATCH_RESULT",
        entity="Match",
        entity_id=match.id,
        summary={"state": match.state.value, "home": match.home_score, "away": match.away_score},
    )
    return match


@router.post("/markets", response_model=MarketRead, status_code=status.HTTP_201_CREATED)
def create_market(
    payload: MarketCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN, UserRole.ORGANIZER)),
):
    match = db.get(Match, payload.match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    market = Market(**payload.model_dump())
    db.add(market)
    db.commit()
    db.refresh(market)
    record_audit(
        db,
        user_id=current_user.id,
        action="MARKET_CREATE",
        entity="Market",
        entity_id=market.id,
        summary={"type": market.type.value},
    )
    return market


@router.patch("/markets/{market_id}", response_model=MarketRead)
def update_market_status(
    market_id: int,
    payload: MarketUpdateStatus,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN, UserRole.ORGANIZER)),
):
    market = db.get(Market, market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Mercado no encontrado")
    market.status = payload.status
    if payload.status == MarketStatus.LOCKED and market.match:
        market.match.locked_bool = True
    db.commit()
    db.refresh(market)
    record_audit(
        db,
        user_id=current_user.id,
        action="MARKET_STATUS",
        entity="Market",
        entity_id=market.id,
        summary={"status": market.status.value},
    )
    return market


@router.get("/matches/{match_id}/markets", response_model=list[MarketRead])
def list_markets(match_id: int, db: Session = Depends(get_db)):
    return db.query(Market).filter(Market.match_id == match_id).all()


@router.post("/odds", response_model=OddRead, status_code=status.HTTP_201_CREATED)
def create_odds(
    payload: OddCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN, UserRole.ORGANIZER)),
):
    market = db.get(Market, payload.market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Mercado no encontrado")
    if any(o.selection == payload.selection for o in market.odds):
        raise HTTPException(status_code=400, detail="Selección ya configurada")
    odd = Odd(**payload.model_dump())
    db.add(odd)
    db.commit()
    db.refresh(odd)
    record_audit(
        db,
        user_id=current_user.id,
        action="ODD_CREATE",
        entity="Odd",
        entity_id=odd.id,
        summary={"selection": payload.selection.value, "price": payload.price},
    )
    return odd


@router.get("/markets/{market_id}/odds", response_model=list[OddRead])
def list_odds(market_id: int, db: Session = Depends(get_db)):
    market = db.get(Market, market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Mercado no encontrado")
    return market.odds
