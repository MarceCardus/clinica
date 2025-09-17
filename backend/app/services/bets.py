from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import Date, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.bet import Bet, BetStatus
from app.models.market import Market, MarketStatus, SelectionType
from app.models.match import Match, MatchState
from app.models.wallet import LedgerType
from app.services import ledger
from app.services.audit import record_audit

BETTING_CUTOFF_MINUTES = 10


def validate_market(match: Match, market: Market) -> None:
    if match.state != MatchState.SCHEDULED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Partido no disponible para apuestas")
    if market.status != MarketStatus.OPEN or match.locked_bool:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mercado cerrado")
    if match.scheduled_at - datetime.utcnow() < timedelta(minutes=BETTING_CUTOFF_MINUTES):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mercado cerrado por horario")


def place_bet(
    db: Session,
    *,
    user_id: int,
    market: Market,
    selection: SelectionType,
    stake: Decimal,
) -> Bet:
    match = market.match
    validate_market(match, market)
    today = datetime.utcnow().date()
    stakes_today = (
        db.query(func.coalesce(func.sum(Bet.stake), 0))
        .filter(
            Bet.user_id == user_id,
            func.cast(Bet.placed_at, Date) == today,
        )
        .scalar()
    )
    if Decimal(stakes_today) + stake > Decimal(str(settings.max_daily_stake)):
        raise HTTPException(status_code=400, detail="Límite diario de apuesta alcanzado")
    price = next((Decimal(str(odd.price)) for odd in market.odds if odd.selection == selection), None)
    if price is None:
        raise HTTPException(status_code=400, detail="Cuota no disponible")
    balance = ledger.get_balance(db, user_id)
    if stake > balance:
        raise HTTPException(status_code=400, detail="Saldo insuficiente")
    potential_return = stake * price
    bet = Bet(
        user_id=user_id,
        market_id=market.id,
        selection=selection,
        stake=stake,
        price_at_bet=price,
        potential_return=potential_return,
    )
    db.add(bet)
    db.flush()
    ledger.add_entry(
        db,
        user_id=user_id,
        entry_type=LedgerType.BET,
        amount=-stake,
        ref_table="bets",
        ref_id=bet.id,
    )
    record_audit(
        db,
        user_id=user_id,
        action="BET_PLACED",
        entity="Bet",
        entity_id=bet.id,
        summary={"market": market.id, "selection": selection.value, "stake": str(stake)},
    )
    return bet


def settle_bet(db: Session, bet: Bet, outcome: BetStatus) -> None:
    if bet.status != BetStatus.PLACED:
        return
    bet.status = outcome
    bet.settled_at = datetime.utcnow()
    if outcome == BetStatus.WON:
        ledger.add_entry(
            db,
            user_id=bet.user_id,
            entry_type=LedgerType.BET_WIN,
            amount=bet.potential_return,
            ref_table="bets",
            ref_id=bet.id,
        )
    elif outcome == BetStatus.VOID:
        ledger.add_entry(
            db,
            user_id=bet.user_id,
            entry_type=LedgerType.ADJUST,
            amount=bet.stake,
            ref_table="bets",
            ref_id=bet.id,
        )
    record_audit(
        db,
        user_id=None,
        action="BET_SETTLED",
        entity="Bet",
        entity_id=bet.id,
        summary={"status": outcome.value},
    )
