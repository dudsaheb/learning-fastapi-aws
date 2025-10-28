from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from api.models import SessionLocal, Base, engine
import joblib
import numpy as np
import os
import datetime

router = APIRouter(prefix="/predict", tags=["Prediction"])

# =========================
# 🔧 Ensure tables exist
# =========================
Base.metadata.create_all(bind=engine)

# =========================
# 💾 Database Dependency
# =========================
def get_db():
    """Provides a database session using models.SessionLocal."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

print(f"🗄️  Active database engine URL: {engine.url}")

# =========================
# 🤖 Load ML Model
# =========================
MODEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "model", "model.pkl"))

try:
    model = joblib.load(MODEL_PATH)
    print(f"✅ Model loaded successfully from {MODEL_PATH}")
except Exception as e:
    print(f"❌ Error loading model from {MODEL_PATH}: {e}")
    model = None


# =========================
# 📦 Schema Definitions
# =========================
class InputData(BaseModel):
    area: float
    bedrooms: int
    bathrooms: int


# =========================
# 🔹 Predict Endpoint
# =========================
@router.post("/")
def predict_price(data: InputData):
    """Predict house price using trained ML model."""
    if model is None:
        raise HTTPException(status_code=500, detail="Model not loaded")

    try:
        features = np.array([[data.area, data.bedrooms, data.bathrooms]])
        predicted_price = model.predict(features)[0]
        return {"predicted_price": round(float(predicted_price), 2)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {e}")


# =========================
# 🧠 Model Info Endpoint
# =========================
@router.get("/info")
def model_info():
    """Return metadata about the ML model."""
    return {
        "model_name": "Linear Regression",
        "framework": "scikit-learn",
        "trained_on": "2025-10-27",
        "status": "active",
        "path": MODEL_PATH,
    }


# =========================
# 🪣 Log Predictions to DB
# =========================
@router.post("/log")
def log_prediction(data: dict, db: Session = Depends(get_db)):
    """
    Log prediction request and response to DB for analytics.
    Creates 'prediction_logs' table dynamically if not exists.
    Works with both SQLite (local) and PostgreSQL (AWS).
    """
    try:
        # Detect if running on SQLite
        is_sqlite = "sqlite" in str(db.bind.url)

        # ✅ Create table dynamically depending on DB type
        if is_sqlite:
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS prediction_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    area FLOAT,
                    bedrooms INT,
                    bathrooms INT,
                    predicted_price FLOAT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
        else:
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS prediction_logs (
                    id SERIAL PRIMARY KEY,
                    area FLOAT,
                    bedrooms INT,
                    bathrooms INT,
                    predicted_price FLOAT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
        db.commit()

        # ✅ Insert prediction data
        if is_sqlite:
            db.execute(text("""
                INSERT INTO prediction_logs (area, bedrooms, bathrooms, predicted_price)
                VALUES (:area, :bedrooms, :bathrooms, :predicted_price);
            """), {
                "area": data.get("area"),
                "bedrooms": data.get("bedrooms"),
                "bathrooms": data.get("bathrooms"),
                "predicted_price": data.get("predicted_price")
            })
            db.commit()

            # ✅ Fetch last inserted ID and timestamp in SQLite
            last_id = db.execute(text("SELECT last_insert_rowid();")).scalar()
            result = db.execute(text("SELECT created_at FROM prediction_logs WHERE id = :id;"), {"id": last_id})
            row = result.fetchone()

            created_at_value = row[0] if row and row[0] else None
            # ✅ Fallback if SQLite hasn’t updated created_at yet
            if not created_at_value:
                created_at_value = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            return {
                "status": "logged",
                "id": last_id,
                "created_at": created_at_value,
                "message": "Prediction logged successfully (SQLite)"
            }

        else:
            # ✅ PostgreSQL with RETURNING clause
            result = db.execute(text("""
                INSERT INTO prediction_logs (area, bedrooms, bathrooms, predicted_price)
                VALUES (:area, :bedrooms, :bathrooms, :predicted_price)
                RETURNING id, created_at;
            """), {
                "area": data.get("area"),
                "bedrooms": data.get("bedrooms"),
                "bathrooms": data.get("bathrooms"),
                "predicted_price": data.get("predicted_price")
            })
            db.commit()
            row = result.fetchone()

            return {
                "status": "logged",
                "id": row[0] if row else None,
                "created_at": row[1] if row else None,
                "message": "Prediction logged successfully (PostgreSQL)"
            }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB log error: {e}")


# =========================
# 📊 Fetch Recent Predictions
# =========================
@router.get("/history")
def get_recent_predictions(limit: int = 10, db: Session = Depends(get_db)):
    """
    Fetch the most recent prediction logs for analytics dashboard.
    Works reliably on SQLite and PostgreSQL.
    """
    try:
        # Fetch all rows (raw SQL)
        result = db.execute(text("""
            SELECT id, area, bedrooms, bathrooms, predicted_price, created_at
            FROM prediction_logs
            ORDER BY id DESC
            LIMIT :limit;
        """), {"limit": limit}).fetchall()

        # Convert rows safely (support both tuple and mapping)
        rows = []
        for row in result:
            try:
                # Modern SQLAlchemy RowMapping object
                rows.append({
                    "id": int(row._mapping["id"]) if row._mapping["id"] is not None else None,
                    "area": float(row._mapping["area"]),
                    "bedrooms": int(row._mapping["bedrooms"]),
                    "bathrooms": int(row._mapping["bathrooms"]),
                    "predicted_price": float(row._mapping["predicted_price"]),
                    "created_at": str(row._mapping["created_at"]),
                })
            except Exception:
                # Fallback for SQLite returning tuples
                rows.append({
                    "id": int(row[0]) if row[0] is not None else None,
                    "area": float(row[1]),
                    "bedrooms": int(row[2]),
                    "bathrooms": int(row[3]),
                    "predicted_price": float(row[4]),
                    "created_at": str(row[5]),
                })

        return rows

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching history: {e}")
