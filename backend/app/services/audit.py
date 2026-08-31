import hashlib
import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def record_audit(
    db: Session,
    *,
    user_id: Optional[int],
    action: str,
    entity: str,
    entity_id: Optional[int],
    summary: dict[str, Any],
    ip: Optional[str] = None,
    ua: Optional[str] = None,
) -> AuditLog:
    payload = json.dumps(summary, sort_keys=True)
    hash_value = hashlib.sha256(payload.encode()).hexdigest()
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        summary=payload[:500],
        ip=ip,
        ua=ua,
        hash=hash_value,
    )
    db.add(log)
    db.flush()
    return log
