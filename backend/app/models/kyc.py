from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import Base


class KYC(Base):
    __tablename__ = "kyc"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    doc_type = Column(String(50), nullable=True)
    doc_number = Column(String(50), nullable=True)
    doc_image_url = Column(String(255), nullable=True)
    verified_bool = Column(Boolean, default=False)
    verified_at = Column(DateTime, nullable=True)

    user = relationship("User", backref="kyc")
