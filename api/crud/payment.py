from sqlalchemy.orm import Session
from decimal import Decimal
from api.models import Payment
from api.schemas.payment import PaymentCreate

def create_payment(db: Session, payment_in: PaymentCreate) -> Payment:
    payment = Payment(
        user_id=payment_in.user_id,
        amount=Decimal(str(payment_in.amount)),
        currency=payment_in.currency or "INR",
        description=payment_in.description,
        status="PAID"  # Or logic to determine status
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment

def get_payment(db: Session, payment_id: int):
    return db.query(Payment).filter(Payment.id == payment_id).first()
