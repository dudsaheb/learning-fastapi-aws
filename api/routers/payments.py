from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from api.dependencies.deps import get_db  # your DB dependency
from api.models import Payment

router = APIRouter(
    prefix='/payments',
    tags=['Payments']
)

@router.get("/payments/{user_id}")
def payment_history(user_id: int, db: Session = Depends(get_db)):
    payments = db.query(Payment).filter(Payment.user_id == user_id).order_by(Payment.created_at.desc()).all()
    return [
        {
            "id": p.id,
            "amount": p.amount,
            "currency": p.currency,
            "status": p.status,
            "created_at": p.created_at,
            "updated_at": p.updated_at
        }
        for p in payments
    ]
