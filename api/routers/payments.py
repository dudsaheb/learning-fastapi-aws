from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from api.models import SessionLocal
from api.schemas.payment import PaymentCreate, PaymentResponse, PaymentOut
from api.crud.payment import create_payment, get_payment

import boto3
import json
import os


router = APIRouter(prefix="/payments", tags=["payments"])

# ======= Dependency for DB session =======
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ======= SQS Configuration =======
QUEUE_URL = os.getenv("SQS_QUEUE_URL")
sqs = boto3.client(
    "sqs",
    region_name="us-east-1",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

# ======= DB Payment Endpoint =======
@router.post("/", response_model=PaymentResponse)
def add_payment(payment_in: PaymentCreate, db: Session = Depends(get_db)):
    """
    Save payment to DB **only** (for reference)
    """
    try:
        payment = create_payment(db, payment_in)
        return PaymentResponse(success=True, payment_id=payment.id, message="Payment recorded")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ======= SQS Queue Endpoint =======
@router.post("/queue/")
async def create_payment_queue(payment: PaymentCreate):
    """
    Send payment message to AWS SQS queue.
    """
    try:
        payment_dict = payment.dict()
        response = sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps(payment_dict)
        )
        return {"status": "queued", "message_id": response['MessageId']}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ======= Get Payment by ID =======
@router.get("/{payment_id}", response_model=PaymentOut)
def read_payment(payment_id: int, db: Session = Depends(get_db)):
    payment = get_payment(db, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment

