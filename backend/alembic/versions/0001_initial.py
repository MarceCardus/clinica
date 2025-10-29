"""initial schema"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("dob", sa.Date(), nullable=False),
        sa.Column("role", sa.Enum("admin", "organizer", "user", name="userrole"), nullable=False),
        sa.Column("status", sa.Enum("active", "pending", "disabled", name="userstatus"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "kyc",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("doc_type", sa.String(length=50), nullable=True),
        sa.Column("doc_number", sa.String(length=50), nullable=True),
        sa.Column("doc_image_url", sa.String(length=255), nullable=True),
        sa.Column("verified_bool", sa.Boolean(), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "tournaments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.Enum("DRAFT", "ACTIVE", "FINISHED", name="tournamentstatus"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tournament_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["tournament_id"], ["tournaments.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tournament_id", sa.Integer(), nullable=False),
        sa.Column("home_team_id", sa.Integer(), nullable=False),
        sa.Column("away_team_id", sa.Integer(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("state", sa.Enum("SCHEDULED", "LIVE", "FINISHED", name="matchstate"), nullable=False),
        sa.Column("home_score", sa.SmallInteger(), nullable=True),
        sa.Column("away_score", sa.SmallInteger(), nullable=True),
        sa.Column("locked_bool", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["away_team_id"], ["teams.id"], ),
        sa.ForeignKeyConstraint(["home_team_id"], ["teams.id"], ),
        sa.ForeignKeyConstraint(["tournament_id"], ["tournaments.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "markets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.Enum("1X2", "OVER_UNDER", name="markettype"), nullable=False),
        sa.Column("line", sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column("status", sa.Enum("OPEN", "LOCKED", "SETTLED", name="marketstatus"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "odds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_id", sa.Integer(), nullable=False),
        sa.Column("selection", sa.Enum("HOME", "DRAW", "AWAY", "OVER", "UNDER", name="selectiontype"), nullable=False),
        sa.Column("price", sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "wallet_ledger",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.Enum("TOPUP", "BET", "BET_WIN", "WITHDRAWAL", "ADJUST", name="ledgertype"), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("balance_after", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("ref_table", sa.String(length=50), nullable=True),
        sa.Column("ref_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wallet_user_created", "wallet_ledger", ["user_id", "created_at"], unique=False)

    op.create_table(
        "topups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("bank_name", sa.String(length=255), nullable=False),
        sa.Column("ref_number", sa.String(length=255), nullable=False),
        sa.Column("proof_url", sa.String(length=255), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "APPROVED", "REJECTED", name="topupstatus"), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("unique_hash", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("unique_hash"),
    )

    op.create_table(
        "withdrawals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("bank_alias", sa.String(length=255), nullable=False),
        sa.Column("bank_holder", sa.String(length=255), nullable=False),
        sa.Column("status", sa.Enum("REQUESTED", "PAID", "REJECTED", name="withdrawalstatus"), nullable=False),
        sa.Column("processed_by", sa.Integer(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["processed_by"], ["users.id"], ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "bets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("market_id", sa.Integer(), nullable=False),
        sa.Column("selection", sa.Enum("HOME", "DRAW", "AWAY", "OVER", "UNDER", name="selectiontype"), nullable=False),
        sa.Column("stake", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("price_at_bet", sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column("potential_return", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("status", sa.Enum("PLACED", "WON", "LOST", "VOID", name="betstatus"), nullable=False),
        sa.Column("placed_at", sa.DateTime(), nullable=False),
        sa.Column("settled_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"], ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bets_user", "bets", ["user_id", "placed_at"], unique=False)

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("ip", sa.String(length=50), nullable=True),
        sa.Column("ua", sa.String(length=255), nullable=True),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_index("ix_bets_user", table_name="bets")
    op.drop_table("bets")
    op.drop_table("withdrawals")
    op.drop_table("topups")
    op.drop_index("ix_wallet_user_created", table_name="wallet_ledger")
    op.drop_table("wallet_ledger")
    op.drop_table("odds")
    op.drop_table("markets")
    op.drop_table("matches")
    op.drop_table("teams")
    op.drop_table("tournaments")
    op.drop_table("kyc")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
