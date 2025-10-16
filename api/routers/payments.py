from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from api.models import SessionLocal
from api.schemas.payment import PaymentCreate, PaymentResponse, PaymentOut
from api.crud.payment import create_payment, get_payment

import boto3
import json
import os
import random
import logging

# ======= Router Setup =======
router = APIRouter(prefix="/payments", tags=["payments"])

# ======= Logging =======
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    Save payment directly to the DB (reference only)
    Inserts a random amount if not provided.
    """
    try:
        # Assign random amount if missing or zero
        if not payment_in.amount or payment_in.amount <= 0:
            payment_in.amount = round(random.uniform(10, 5000), 2)

        payment = create_payment(db, payment_in)
        logger.info(f"💰 Payment inserted: ID={payment.id}, Amount={payment_in.amount}")

        return PaymentResponse(success=True, payment_id=payment.id, message="Payment recorded")

    except Exception as e:
        logger.error(f"❌ DB Insert Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ======= SQS Queue Endpoint =======
@router.post("/queue/")
async def create_payment_queue(payment: PaymentCreate):
    """
    Send payment message to AWS SQS queue.
    Automatically generates a random amount if not provided.
    """
    try:
        # Add random amount if not specified
        if not payment.amount or payment.amount <= 0:
            payment.amount = round(random.uniform(10, 5000), 2)

        payment_dict = payment.dict()
        response = sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps(payment_dict)
        )

        logger.info(f"📦 Queued payment for user {payment.user_id} | Amount ₹{payment.amount} | MsgID: {response['MessageId']}")
        return {"status": "queued", "message_id": response['MessageId'], "amount": payment.amount}

    except Exception as e:
        logger.error(f"❌ SQS Queue Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ======= Get Payment by ID =======
@router.get("/{payment_id}", response_model=PaymentOut)
def read_payment(payment_id: int, db: Session = Depends(get_db)):
    """
    Fetch payment record by ID.
    """
    try:
        payment = get_payment(db, payment_id)
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")

        logger.info(f"📄 Payment retrieved: ID={payment.id}, Amount={payment.amount}")
        return payment

    except Exception as e:
        logger.error(f"❌ Read Payment Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
