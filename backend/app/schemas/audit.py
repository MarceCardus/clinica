from datetime import datetime

from pydantic import BaseModel


class AuditLogRead(BaseModel):
    id: int
    user_id: int | None
    action: str
    entity: str
    entity_id: int | None
    summary: str
    ip: str | None
    ua: str | None
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }
