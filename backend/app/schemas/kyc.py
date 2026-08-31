from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class KYCBase(BaseModel):
    doc_type: Optional[str] = Field(default=None, max_length=50)
    doc_number: Optional[str] = Field(default=None, max_length=50)
    doc_image_url: Optional[str] = None
    verified_bool: Optional[bool] = False
    verified_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True,
    }


class KYCUpdate(BaseModel):
    doc_type: Optional[str]
    doc_number: Optional[str]
    doc_image_url: Optional[str]
