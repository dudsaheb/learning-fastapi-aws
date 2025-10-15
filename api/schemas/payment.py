from pydantic import BaseModel, constr, condecimal, Field
from typing import Optional
from datetime import datetime

class PaymentCreate(BaseModel):
    user_id: int
    amount: condecimal(gt=0, max_digits=12, decimal_places=2)
    currency: Optional[str] = "INR"
    description: Optional[str] = None

class PaymentResponse(BaseModel):
    success: bool
    payment_id: Optional[int]
    message: Optional[str]

class PaymentOut(BaseModel):
    id: int
    user_id: int
    amount: float
    currency: str
    status: str
    description: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True


class PaymentRecord(BaseModel):
    id: int
    user_id: int
    amount: float
    currency: str
    description: str
    created_at: datetime  # make sure your payments table has this column