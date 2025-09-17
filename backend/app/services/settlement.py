from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.bet import BetStatus
from app.models.market import Market, MarketStatus, MarketType, SelectionType
from app.models.match import Match, MatchState
from app.services.audit import record_audit
from app.services.bets import settle_bet


def lock_markets(db: Session, match: Match) -> None:
    for market in match.markets:
        if market.status == MarketStatus.OPEN:
            market.status = MarketStatus.LOCKED
    match.locked_bool = True


def settle_match(db: Session, match: Match) -> None:
    if match.state != MatchState.FINISHED:
        raise ValueError("El partido debe estar finalizado")
    for market in match.markets:
        if market.status == MarketStatus.SETTLED:
            continue
        winning = determine_winner(market, match)
        for bet in market.bets:
            outcome = BetStatus.LOST
            if winning is None:
                outcome = BetStatus.VOID
            elif bet.selection == winning:
                outcome = BetStatus.WON
            settle_bet(db, bet, outcome)
        market.status = MarketStatus.SETTLED
        record_audit(
            db,
            user_id=None,
            action="MARKET_SETTLED",
            entity="Market",
            entity_id=market.id,
            summary={"status": market.status.value},
        )
    db.flush()


def determine_winner(market: Market, match: Match) -> SelectionType | None:
    if market.type == MarketType.ONE_X_TWO:
        if match.home_score > match.away_score:
            return SelectionType.HOME
        if match.home_score < match.away_score:
            return SelectionType.AWAY
        return SelectionType.DRAW
    if market.type == MarketType.OVER_UNDER and market.line is not None:
        total_goals = Decimal(match.home_score + match.away_score)
        if total_goals > Decimal(market.line):
            return SelectionType.OVER
        if total_goals < Decimal(market.line):
            return SelectionType.UNDER
        return None
    return None
