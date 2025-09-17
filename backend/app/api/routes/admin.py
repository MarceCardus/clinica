from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.audit import AuditLog
from app.models.user import UserRole
from app.schemas.audit import AuditLogRead

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit", response_model=list[AuditLogRead])
def list_audit(
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN)),
):
    query = db.query(AuditLog)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if start:
        query = query.filter(AuditLog.created_at >= start)
    if end:
        query = query.filter(AuditLog.created_at <= end)
    return query.order_by(AuditLog.created_at.desc()).limit(200).all()
