from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.models.kyc import KYC
from app.schemas.kyc import KYCBase, KYCUpdate

router = APIRouter(prefix="/kyc", tags=["kyc"])


@router.get("/me", response_model=KYCBase)
def read_my_kyc(db: Session = Depends(get_db), current_user=Depends(get_current_active_user)):
    kyc = db.query(KYC).filter(KYC.user_id == current_user.id).first()
    if not kyc:
        kyc = KYC(user_id=current_user.id)
        db.add(kyc)
        db.commit()
        db.refresh(kyc)
    return kyc


@router.put("/me", response_model=KYCBase)
def update_my_kyc(payload: KYCUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_active_user)):
    kyc = db.query(KYC).filter(KYC.user_id == current_user.id).first()
    if not kyc:
        kyc = KYC(user_id=current_user.id)
        db.add(kyc)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(kyc, field, value)
    db.commit()
    db.refresh(kyc)
    return kyc
