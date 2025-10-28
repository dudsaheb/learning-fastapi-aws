from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from api.models import SessionLocal, Base, engine
import joblib
import numpy as np
import os
import datetime
import json

router = APIRouter(prefix="/predict", tags=["Prediction"])

# ====================================================
# 🗄️  Database Setup
# ====================================================
Base.metadata.create_all(bind=engine)

def get_db():
    """Provide a SQLAlchemy database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

print(f"🗄️  Active database engine URL: {engine.url}")

# ====================================================
# 🤖 Load ML Model
# ====================================================
MODEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "model", "model.pkl"))
MODEL_INFO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "model", "model_info.json"))

try:
    model = joblib.load(MODEL_PATH)
    print(f"✅ Model loaded successfully from {MODEL_PATH}")
except Exception as e:
    print(f"❌ Error loading model from {MODEL_PATH}: {e}")
    model = None

# Try loading metadata
try:
    with open(MODEL_INFO_PATH, "r") as f:
        model_info_data = json.load(f)
except Exception:
    model_info_data = {
        "model_name": "Linear Regression",
        "framework": "scikit-learn",
        "trained_on": "unknown",
        "status": "unknown",
    }

# ====================================================
# 🧩 Pydantic Schemas
# ====================================================
class InputData(BaseModel):
    area: float
    bedrooms: int
    bathrooms: int

class LogData(InputData):
    predicted_price: float


# ====================================================
# 🔮 Predict Endpoint
# ====================================================
@router.post("/")
def predict_price(data: InputData):
    """Predict house price using the trained ML model."""
    if model is None:
        raise HTTPException(status_code=500, detail="Model not loaded")

    try:
        features = np.array([[data.area, data.bedrooms, data.bathrooms]])
        predicted_price_lakh = model.predict(features)[0]
        predicted_price_inr = predicted_price_lakh * 100000  # ✅ Convert Lakhs → ₹

        return {
            "area": data.area,
            "bedrooms": data.bedrooms,
            "bathrooms": data.bathrooms,
            "predicted_price": round(float(predicted_price_inr), 2),
            "currency": "INR",
            "message": "Prediction successful"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {e}")


# ====================================================
# 🧠 Model Info Endpoint
# ====================================================
@router.get("/info")
def model_info():
    """Return model metadata."""
    model_info_data["path"] = MODEL_PATH
    model_info_data["status"] = "active" if model else "not loaded"
    return model_info_data


# ====================================================
# 💾 Log Prediction
# ====================================================
@router.post("/log")
def log_prediction(data: LogData, db: Session = Depends(get_db)):
    """
    Log prediction request and result into database.
    Works with both SQLite and PostgreSQL.
    """
    try:
        is_sqlite = "sqlite" in str(db.bind.url)

        # ✅ Ensure table exists
        create_table_sql = """
            CREATE TABLE IF NOT EXISTS prediction_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                area FLOAT,
                bedrooms INT,
                bathrooms INT,
                predicted_price FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """ if is_sqlite else """
            CREATE TABLE IF NOT EXISTS prediction_logs (
                id SERIAL PRIMARY KEY,
                area FLOAT,
                bedrooms INT,
                bathrooms INT,
                predicted_price FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """
        db.execute(text(create_table_sql))
        db.commit()

        # ✅ Insert data
        if is_sqlite:
            db.execute(text("""
                INSERT INTO prediction_logs (area, bedrooms, bathrooms, predicted_price)
                VALUES (:area, :bedrooms, :bathrooms, :predicted_price)
            """), data.dict())
            db.commit()
            last_id = db.execute(text("SELECT last_insert_rowid();")).scalar()
            created_at = db.execute(text("SELECT created_at FROM prediction_logs WHERE id = :id;"), {"id": last_id}).scalar()
        else:
            result = db.execute(text("""
                INSERT INTO prediction_logs (area, bedrooms, bathrooms, predicted_price)
                VALUES (:area, :bedrooms, :bathrooms, :predicted_price)
                RETURNING id, created_at
            """), data.dict())
            db.commit()
            row = result.fetchone()
            last_id, created_at = (row[0], row[1]) if row else (None, None)

        return {
            "status": "logged",
            "id": last_id,
            "created_at": str(created_at),
            "message": f"Prediction logged successfully ({'SQLite' if is_sqlite else 'PostgreSQL'})"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB log error: {e}")


# ====================================================
# 📜 Fetch Prediction History
# ====================================================
@router.get("/history")
def get_recent_predictions(limit: int = 10, db: Session = Depends(get_db)):
    """Fetch latest predictions."""
    try:
        result = db.execute(text("""
            SELECT id, area, bedrooms, bathrooms, predicted_price, created_at
            FROM prediction_logs
            ORDER BY id DESC
            LIMIT :limit
        """), {"limit": limit}).fetchall()

        records = []
        for row in result:
            row_map = getattr(row, "_mapping", None)
            if row_map:
                # SQLAlchemy 2.x RowMapping
                records.append({
                    "id": row_map.get("id"),
                    "area": row_map.get("area"),
                    "bedrooms": row_map.get("bedrooms"),
                    "bathrooms": row_map.get("bathrooms"),
                    "predicted_price": row_map.get("predicted_price"),
                    "created_at": str(row_map.get("created_at")),
                })
            else:
                # SQLite tuple fallback
                records.append({
                    "id": row[0],
                    "area": row[1],
                    "bedrooms": row[2],
                    "bathrooms": row[3],
                    "predicted_price": row[4],
                    "created_at": str(row[5]),
                })

        return records

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching history: {e}")
