from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import UserRole, UserStatus


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    dob: date

    @field_validator("dob")
    @classmethod
    def validate_age(cls, v: date) -> date:
        today = date.today()
        age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
        if age < 18:
            raise ValueError("Debe ser mayor de 18 años")
        return v


class UserCreate(UserBase):
    password: str = Field(min_length=8)


class UserRead(UserBase):
    id: int
    role: UserRole
    status: UserStatus
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class UserUpdateRole(BaseModel):
    role: UserRole
    status: Optional[UserStatus] = None
