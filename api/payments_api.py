# api/payments_api.py
from fastapi import APIRouter, HTTPException
from typing import List
from sqlalchemy import create_engine, text
from api.schemas.payment import PaymentRecord
import os

router = APIRouter()

# Database connection URL
DATABASE_URL = os.getenv("DB_URL")  # e.g. postgresql://user:password@host:5432/postgres
engine = create_engine(DATABASE_URL)

@router.get("/latest-payments/", response_model=List[PaymentRecord])
def get_latest_payments(limit: int = 1000):
    """
    Open GET API to fetch the latest 'limit' payments in descending order.
    """
    try:
        query = text("""
            SELECT id, user_id, amount, currency, description, created_at
            FROM payments
            ORDER BY created_at DESC
            LIMIT :limit
        """)

        with engine.connect() as conn:
            result = conn.execute(query, {"limit": limit})
            rows = result.fetchall()

        # Convert SQLAlchemy rows to list of dicts
        payments = [PaymentRecord(**dict(row._mapping)) for row in rows]
        return payments

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")
