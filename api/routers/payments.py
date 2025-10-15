from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from api.models import SessionLocal
from api.schemas.payment import PaymentCreate, PaymentResponse, PaymentOut
from api.crud.payment import create_payment, get_payment

router = APIRouter(prefix="/payments", tags=["payments"])

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/", response_model=PaymentResponse)
def add_payment(payment_in: PaymentCreate, db: Session = Depends(get_db)):
    try:
        payment = create_payment(db, payment_in)
        return PaymentResponse(success=True, payment_id=payment.id, message="Payment recorded")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{payment_id}", response_model=PaymentOut)
def read_payment(payment_id: int, db: Session = Depends(get_db)):
    payment = get_payment(db, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment
