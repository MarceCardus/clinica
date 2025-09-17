from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.market import Market, MarketStatus, MarketType, Odd, SelectionType
from app.models.match import Match, MatchState
from app.models.team import Team
from app.models.tournament import Tournament, TournamentStatus
from app.models.user import User, UserRole, UserStatus


def get_or_create_admin(db: Session) -> User:
    admin = db.query(User).filter(User.email == settings.admin_email).first()
    if admin:
        return admin
    admin = User(
        email=settings.admin_email,
        full_name="Administrador",
        dob=datetime(1990, 1, 1).date(),
        password_hash=get_password_hash(settings.admin_password),
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def seed_tournament(db: Session) -> None:
    if db.query(Tournament).count() > 0:
        return
    now = datetime.utcnow()
    tournament = Tournament(
        name="Liga Interna",
        company_name=settings.seed_company,
        starts_at=now,
        ends_at=now + timedelta(days=7),
        status=TournamentStatus.ACTIVE,
    )
    db.add(tournament)
    db.flush()

    team_a = Team(tournament_id=tournament.id, name="Recursos Humanos")
    team_b = Team(tournament_id=tournament.id, name="Marketing")
    team_c = Team(tournament_id=tournament.id, name="Finanzas")
    team_d = Team(tournament_id=tournament.id, name="Ventas")
    db.add_all([team_a, team_b, team_c, team_d])
    db.flush()

    match1 = Match(
        tournament_id=tournament.id,
        home_team_id=team_a.id,
        away_team_id=team_b.id,
        scheduled_at=now + timedelta(days=1),
        state=MatchState.SCHEDULED,
    )
    match2 = Match(
        tournament_id=tournament.id,
        home_team_id=team_c.id,
        away_team_id=team_d.id,
        scheduled_at=now + timedelta(days=2),
        state=MatchState.SCHEDULED,
    )
    match3 = Match(
        tournament_id=tournament.id,
        home_team_id=team_a.id,
        away_team_id=team_c.id,
        scheduled_at=now + timedelta(days=3),
        state=MatchState.SCHEDULED,
    )
    db.add_all([match1, match2, match3])
    db.flush()

    for match in [match1, match2, match3]:
        market = Market(
            match_id=match.id,
            type=MarketType.ONE_X_TWO,
            status=MarketStatus.OPEN,
        )
        db.add(market)
        db.flush()
        odds = [
            Odd(market_id=market.id, selection=SelectionType.HOME, price=Decimal("1.80")),
            Odd(market_id=market.id, selection=SelectionType.DRAW, price=Decimal("3.00")),
            Odd(market_id=market.id, selection=SelectionType.AWAY, price=Decimal("2.20")),
        ]
        db.add_all(odds)

        over_under = Market(
            match_id=match.id,
            type=MarketType.OVER_UNDER,
            line=Decimal("2.5"),
            status=MarketStatus.OPEN,
        )
        db.add(over_under)
        db.flush()
        db.add_all(
            [
                Odd(market_id=over_under.id, selection=SelectionType.OVER, price=Decimal("1.95")),
                Odd(market_id=over_under.id, selection=SelectionType.UNDER, price=Decimal("1.90")),
            ]
        )

    db.commit()


if __name__ == "__main__":
    with SessionLocal() as session:
        get_or_create_admin(session)
        seed_tournament(session)
