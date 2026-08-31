from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import Date, func
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db, require_role
from app.core.config import settings
from app.models.topup import TopUp, TopUpStatus
from app.models.user import UserRole
from app.models.wallet import LedgerType, WalletLedger
from app.models.withdrawal import Withdrawal, WithdrawalStatus
from app.schemas.wallet import (
    BalanceResponse,
    TopUpRead,
    TopUpReview,
    WalletEntry,
    WithdrawalCreate,
    WithdrawalRead,
    WithdrawalReview,
)
from app.services import ledger
from app.services.audit import record_audit
from app.services.storage import storage_service

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("/balance/me", response_model=BalanceResponse)
def get_my_balance(db: Session = Depends(get_db), current_user=Depends(get_current_active_user)):
    balance = ledger.get_balance(db, current_user.id)
    return BalanceResponse(balance=balance)


@router.get("/ledger/me", response_model=list[WalletEntry])
def get_my_ledger(db: Session = Depends(get_db), current_user=Depends(get_current_active_user)):
    entries = (
        db.query(WalletLedger)
        .filter(WalletLedger.user_id == current_user.id)
        .order_by(WalletLedger.created_at.desc())
        .all()
    )
    return entries


@router.get("/topups/me", response_model=list[TopUpRead])
def get_my_topups(db: Session = Depends(get_db), current_user=Depends(get_current_active_user)):
    return (
        db.query(TopUp)
        .filter(TopUp.user_id == current_user.id)
        .order_by(TopUp.created_at.desc())
        .all()
    )


@router.post("/topups", response_model=TopUpRead, status_code=status.HTTP_201_CREATED)
def create_topup(
    amount: Decimal = Form(...),
    bank_name: str = Form(...),
    ref_number: str = Form(...),
    proof: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    today = datetime.utcnow().date()
    total_today = (
        db.query(func.coalesce(func.sum(TopUp.amount), 0))
        .filter(
            TopUp.user_id == current_user.id,
            func.cast(TopUp.created_at, Date) == today,
        )
        .scalar()
    )
    if Decimal(total_today) + amount > Decimal(str(settings.max_daily_topup)):
        raise HTTPException(status_code=400, detail="Límite diario de recarga alcanzado")

    content = read_file(proof)
    url, digest = storage_service.upload(
        content=content,
        filename=proof.filename or "comprobante",
        content_type=proof.content_type or "application/octet-stream",
    )
    existing = db.query(TopUp).filter(TopUp.unique_hash == digest).first()
    if existing:
        raise HTTPException(status_code=400, detail="Comprobante duplicado")
    topup = TopUp(
        user_id=current_user.id,
        amount=amount,
        bank_name=bank_name,
        ref_number=ref_number,
        proof_url=url,
        unique_hash=digest,
    )
    db.add(topup)
    db.commit()
    db.refresh(topup)
    record_audit(
        db,
        user_id=current_user.id,
        action="TOPUP_CREATE",
        entity="TopUp",
        entity_id=topup.id,
        summary={"amount": str(amount), "ref": ref_number},
    )
    return topup


def read_file(file: UploadFile) -> bytes:
    content = file.file.read()
    file.file.close()
    if not content:
        raise HTTPException(status_code=400, detail="Archivo inválido")
    return content


@router.patch("/topups/{topup_id}", response_model=TopUpRead)
def review_topup(
    topup_id: int,
    payload: TopUpReview,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN, UserRole.ORGANIZER)),
):
    topup = db.get(TopUp, topup_id)
    if not topup:
        raise HTTPException(status_code=404, detail="Recarga no encontrada")
    if topup.status != TopUpStatus.PENDING:
        raise HTTPException(status_code=400, detail="Recarga ya revisada")
    topup.status = payload.status
    topup.reviewed_by = current_user.id
    topup.reviewed_at = datetime.utcnow()
    if payload.status == TopUpStatus.APPROVED:
        ledger.add_entry(
            db,
            user_id=topup.user_id,
            entry_type=LedgerType.TOPUP,
            amount=Decimal(topup.amount),
            ref_table="topups",
            ref_id=topup.id,
        )
    db.commit()
    db.refresh(topup)
    record_audit(
        db,
        user_id=current_user.id,
        action="TOPUP_REVIEW",
        entity="TopUp",
        entity_id=topup.id,
        summary={"status": payload.status.value},
    )
    return topup


@router.post("/withdrawals", response_model=WithdrawalRead, status_code=status.HTTP_201_CREATED)
def create_withdrawal(
    payload: WithdrawalCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    balance = ledger.get_balance(db, current_user.id)
    if payload.amount > balance:
        raise HTTPException(status_code=400, detail="Saldo insuficiente")
    withdrawal = Withdrawal(
        user_id=current_user.id,
        amount=payload.amount,
        bank_alias=payload.bank_alias,
        bank_holder=payload.bank_holder,
    )
    db.add(withdrawal)
    db.commit()
    db.refresh(withdrawal)
    record_audit(
        db,
        user_id=current_user.id,
        action="WITHDRAW_REQUEST",
        entity="Withdrawal",
        entity_id=withdrawal.id,
        summary={"amount": str(payload.amount)},
    )
    return withdrawal


@router.get("/withdrawals/me", response_model=list[WithdrawalRead])
def get_my_withdrawals(db: Session = Depends(get_db), current_user=Depends(get_current_active_user)):
    return (
        db.query(Withdrawal)
        .filter(Withdrawal.user_id == current_user.id)
        .order_by(Withdrawal.created_at.desc())
        .all()
    )


@router.patch("/withdrawals/{withdrawal_id}", response_model=WithdrawalRead)
def process_withdrawal(
    withdrawal_id: int,
    payload: WithdrawalReview,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN)),
):
    withdrawal = db.get(Withdrawal, withdrawal_id)
    if not withdrawal:
        raise HTTPException(status_code=404, detail="Retiro no encontrado")
    if withdrawal.status != WithdrawalStatus.REQUESTED:
        raise HTTPException(status_code=400, detail="Retiro ya procesado")
    withdrawal.status = payload.status
    withdrawal.processed_by = current_user.id
    withdrawal.processed_at = datetime.utcnow()
    if payload.status == WithdrawalStatus.PAID:
        ledger.add_entry(
            db,
            user_id=withdrawal.user_id,
            entry_type=LedgerType.WITHDRAWAL,
            amount=Decimal(-withdrawal.amount),
            ref_table="withdrawals",
            ref_id=withdrawal.id,
        )
    db.commit()
    db.refresh(withdrawal)
    record_audit(
        db,
        user_id=current_user.id,
        action="WITHDRAW_PROCESS",
        entity="Withdrawal",
        entity_id=withdrawal.id,
        summary={"status": payload.status.value},
    )
    return withdrawal


@router.post("/bank/webhook", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def bank_webhook_stub():
    return {"message": "Integración bancaria pendiente"}


@router.get("/topups", response_model=list[TopUpRead])
def list_all_topups(
    status: TopUpStatus | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN, UserRole.ORGANIZER)),
):
    query = db.query(TopUp)
    if status:
        query = query.filter(TopUp.status == status)
    return query.order_by(TopUp.created_at.desc()).all()


@router.get("/withdrawals", response_model=list[WithdrawalRead])
def list_all_withdrawals(
    status: WithdrawalStatus | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN, UserRole.ORGANIZER)),
):
    query = db.query(Withdrawal)
    if status:
        query = query.filter(Withdrawal.status == status)
    return query.order_by(Withdrawal.created_at.desc()).all()
