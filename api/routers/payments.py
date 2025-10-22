from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from api.models import SessionLocal
from api.schemas.payment import PaymentCreate, PaymentResponse, PaymentOut
from api.crud.payment import create_payment, get_payment
from sqlalchemy import text

import boto3
import json
import os
import random
import logging
from typing import List

# ======= Router Setup =======
router = APIRouter(prefix="/payments", tags=["payments"])

# ======= Logging Setup =======
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
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
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# sqs = boto3.client(
#     "sqs",
#     region_name=AWS_REGION,
#     aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
#     aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
# )

sqs = boto3.client("sqs", region_name=AWS_REGION)

# ======= CONSTANT USER ID =======
DEFAULT_USER_ID = 32

# ======= 1️⃣ Direct DB Payment Insert =======
@router.post("/", response_model=PaymentResponse)
def add_payment(payment_in: PaymentCreate, db: Session = Depends(get_db)):
    """
    Save a payment directly into the database for user_id=32.
    Inserts a random amount if not provided.
    """
    try:
        payment_in.user_id = DEFAULT_USER_ID  # 👈 Always use user_id = 32

        if not payment_in.amount or payment_in.amount <= 0:
            payment_in.amount = round(random.uniform(10, 5000), 2)

        payment = create_payment(db, payment_in)
        logger.info(f"💰 Payment inserted: ID={payment.id}, User={payment_in.user_id}, Amount={payment_in.amount}")

        return PaymentResponse(success=True, payment_id=payment.id, message="Payment recorded successfully")

    except Exception as e:
        logger.error(f"❌ DB Insert Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ======= 2️⃣ Queue Single Payment to SQS =======
@router.post("/queue/")
async def create_payment_queue(payment: PaymentCreate):
    """
    Send a single payment message to AWS SQS queue for user_id=32.
    Randomizes amount if not provided.
    """
    try:
        payment.user_id = DEFAULT_USER_ID  # 👈 Always use user_id = 32

        if not payment.amount or float(payment.amount) <= 0:
            payment.amount = round(random.uniform(10, 5000), 2)

        # ✅ Ensure amount is serializable (convert to float)
        payment_dict = payment.dict()
        payment_dict["amount"] = float(payment_dict["amount"])

        message_body = json.dumps(payment_dict)
        response = sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=message_body)

        logger.info(f"📦 Queued payment | User={payment.user_id} | Amount=₹{payment.amount} | MsgID={response['MessageId']}")
        return {
            "status": "queued",
            "message_id": response["MessageId"],
            "user_id": payment.user_id,
            "amount": payment.amount
        }

    except Exception as e:
        logger.error(f"❌ SQS Queue Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# ======= 3️⃣ Queue Bulk Payments to SQS =======
@router.post("/queue/bulk/")
async def create_bulk_payments(batch_size: int = 10):
    """
    Sends multiple SQS batches of up to 10 messages each.
    """
    try:
        if batch_size < 1:
            raise HTTPException(status_code=400, detail="Batch size must be at least 1.")

        total_messages = batch_size
        messages = []

        for i in range(total_messages):
            payment_data = {
                "user_id": 32,
                "amount": round(random.uniform(10, 5000), 2),
                "currency": "INR",
                "status": "SUCCESS",
                "description": f"Auto-generated batch payment #{i+1}"
            }
            messages.append({"Id": str(i), "MessageBody": json.dumps(payment_data)})

        # Split into chunks of 10
        success_count = 0
        fail_count = 0
        for j in range(0, len(messages), 10):
            batch = messages[j:j+10]
            resp = sqs.send_message_batch(QueueUrl=QUEUE_URL, Entries=batch)
            success_count += len(resp.get("Successful", []))
            fail_count += len(resp.get("Failed", []))

        logger.info(f"🚀 Sent {success_count} messages, Failed {fail_count}")
        return {"status": "batch_sent", "success": success_count, "failed": fail_count}

    except Exception as e:
        logger.error(f"❌ SQS Batch Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# ======= 4️⃣ Queue Metrics (for frontend) =======
@router.get("/queue/metrics")
def get_queue_metrics():
    """
    Returns real-time SQS queue statistics.
    """
    try:
        attrs = sqs.get_queue_attributes(
            QueueUrl=QUEUE_URL,
            AttributeNames=[
                "ApproximateNumberOfMessages",
                "ApproximateNumberOfMessagesNotVisible",
                "ApproximateNumberOfMessagesDelayed"
            ]
        )
        visible = int(attrs["Attributes"].get("ApproximateNumberOfMessages", 0))
        inflight = int(attrs["Attributes"].get("ApproximateNumberOfMessagesNotVisible", 0))
        delayed = int(attrs["Attributes"].get("ApproximateNumberOfMessagesDelayed", 0))

        logger.info(f"📊 Queue Metrics | Visible={visible}, InFlight={inflight}, Delayed={delayed}")
        return {"visible": visible, "inflight": inflight, "delayed": delayed}

    except Exception as e:
        logger.error(f"❌ Queue Metrics Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ======= 5️⃣ Get Payment by ID =======
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


# ======= 6️⃣ Get Latest Payments =======
# @router.get("/latest/")
# def get_latest_payments(limit: int = 20, db: Session = Depends(get_db)):
#     """
#     Fetch latest payment records in descending order by creation time.
#     """
#     try:
#         payments = db.execute(
#             "SELECT * FROM payments WHERE user_id = :uid ORDER BY created_at DESC LIMIT :limit",
#             {"uid": DEFAULT_USER_ID, "limit": limit}
#         ).fetchall()

#         return [
#             {
#                 "id": p.id,
#                 "user_id": p.user_id,
#                 "amount": p.amount,
#                 "currency": getattr(p, "currency", "INR"),
#                 "description": getattr(p, "description", ""),
#                 "created_at": p.created_at
#             }
#             for p in payments
#         ]
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))



@router.get("/latest/")
def get_latest_payments(limit: int = 20, db: Session = Depends(get_db)):
    """
    Fetch latest payment records (for user_id=32) ordered by creation time.
    Compatible with React dashboard.
    """
    try:
        query = text("""
            SELECT id, user_id, amount, currency, status, description, created_at
            FROM payments
            WHERE user_id = :uid
            ORDER BY created_at DESC
            LIMIT :limit
        """)

        result = db.execute(query, {"uid": DEFAULT_USER_ID, "limit": limit}).fetchall()

        payments = [
            {
                "id": row.id,
                "user_id": row.user_id,
                "amount": float(row.amount),
                "currency": row.currency or "INR",
                "status": row.status or "SUCCESS",
                "description": row.description or "",
                "created_at": row.created_at,
            }
            for row in result
        ]

        return payments

    except Exception as e:
        logger.error(f"❌ Latest Payments Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


