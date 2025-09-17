from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Enum, Integer, String

from app.models.base import Base


class UserRole(str, Enum):  # type: ignore[misc]
    ADMIN = "admin"
    ORGANIZER = "organizer"
    USER = "user"


class UserStatus(str, Enum):  # type: ignore[misc]
    ACTIVE = "active"
    PENDING = "pending"
    DISABLED = "disabled"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    dob = Column(Date, nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.USER)
    status = Column(Enum(UserStatus), nullable=False, default=UserStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
