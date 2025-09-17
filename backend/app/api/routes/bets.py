from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_active_user, get_db
from app.models.bet import Bet
from app.models.market import Market
from app.schemas.bet import BetCreate, BetRead
from app.services.bets import place_bet

router = APIRouter(prefix="/bets", tags=["bets"])


@router.post("", response_model=BetRead)
def create_bet(payload: BetCreate, db: Session = Depends(get_db), current_user=Depends(get_current_active_user)):
    market = (
        db.query(Market)
        .options(joinedload(Market.match), joinedload(Market.odds))
        .filter(Market.id == payload.market_id)
        .first()
    )
    if not market:
        raise HTTPException(status_code=404, detail="Mercado no encontrado")
    bet = place_bet(
        db,
        user_id=current_user.id,
        market=market,
        selection=payload.selection,
        stake=payload.stake,
    )
    db.commit()
    db.refresh(bet)
    return bet


@router.get("/me", response_model=list[BetRead])
def list_my_bets(db: Session = Depends(get_db), current_user=Depends(get_current_active_user)):
    bets = (
        db.query(Bet)
        .filter(Bet.user_id == current_user.id)
        .order_by(Bet.placed_at.desc())
        .all()
    )
    return bets
