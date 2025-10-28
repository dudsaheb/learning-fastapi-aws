# api/agents/property_agent.py
"""
Agent router: Uses OpenAI function-calling to orchestrate tools:
 - search_listings (mock / external API)
 - predict_listing (local ML model)
 - get_history (DB)
 - send_email (mock)

Compatible with new OpenAI SDK (>=1.0.0)
Requires:
  - OPENAI_API_KEY
  - (optional) PROPERTY_API_KEY
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from openai import OpenAI
import os
import json
import requests
from typing import Any, Dict, List, Optional
from api.models import SessionLocal  # DB session factory
from sqlalchemy.orm import Session
from sqlalchemy import text
import joblib
import numpy as np
import logging

# ----------------------------------------------------------
# 🚀 Initialize
# ----------------------------------------------------------
router = APIRouter(prefix="/agent", tags=["Agent"])

# Initialize OpenAI client safely
try:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception:
    client = None

LOGGER = logging.getLogger("property_agent")
LOGGER.setLevel(logging.INFO)

# ----------------------------------------------------------
# 🧠 Load ML Model
# ----------------------------------------------------------
MODEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "model", "model.pkl"))
if os.path.exists(MODEL_PATH):
    try:
        model = joblib.load(MODEL_PATH)
        LOGGER.info(f"✅ Agent: Model loaded successfully from {MODEL_PATH}")
    except Exception as e:
        LOGGER.warning(f"⚠️ Failed to load model: {e}")
        model = None
else:
    LOGGER.warning(f"⚠️ Model file not found at {MODEL_PATH}")
    model = None

# ----------------------------------------------------------
# 📦 Schemas
# ----------------------------------------------------------
class AgentRequest(BaseModel):
    goal: str
    max_listings: Optional[int] = 5
    location: Optional[str] = None


class AgentResponse(BaseModel):
    advice: str
    actions: list


# ----------------------------------------------------------
# 💾 DB Dependency
# ----------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ----------------------------------------------------------
# 🧰 Tools
# ----------------------------------------------------------
# def search_listings_tool(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
#     """Mock property listing search."""
#     PROPERTY_API_KEY = os.getenv("PROPERTY_API_KEY")
#     if PROPERTY_API_KEY:
#         try:
#             resp = requests.get(
#                 "https://api.example.com/search",
#                 params={"q": query, "limit": max_results},
#                 headers={"Authorization": f"Bearer {PROPERTY_API_KEY}"},
#                 timeout=10,
#             )
#             return resp.json().get("results", [])
#         except Exception as e:
#             LOGGER.warning(f"search_listings_tool error: {e}")

#     return [
#         {"id": "L1", "title": "3BHK in South Bangalore", "price": 8500000, "area": 1200, "bedrooms": 3, "bathrooms": 2},
#         {"id": "L2", "title": "2BHK near MG Road", "price": 7200000, "area": 950, "bedrooms": 2, "bathrooms": 1},
#         {"id": "L3", "title": "4BHK independent house", "price": 16000000, "area": 2500, "bedrooms": 4, "bathrooms": 3},
#         {"id": "L4", "title": "3BHK apartment - outskirts", "price": 5500000, "area": 1400, "bedrooms": 3, "bathrooms": 2},
#         {"id": "L5", "title": "2BHK resale", "price": 4800000, "area": 800, "bedrooms": 2, "bathrooms": 1},
#     ][:max_results]

import random

def search_listings_tool(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Generate mock property listings dynamically based on city or query.
    """
    query_lower = query.lower()

    # City-specific templates
    listings_data = {
        "bangalore": [
            ("Indiranagar", 9500000, 1200),
            ("Whitefield", 8700000, 1100),
            ("Koramangala", 12500000, 1400),
            ("HSR Layout", 9900000, 1300),
            ("JP Nagar", 8800000, 1150),
            ("Electronic City", 7000000, 1050),
            ("Yelahanka", 7500000, 1200),
            ("BTM Layout", 9200000, 1250),
            ("Hebbal", 9700000, 1280),
            ("Marathahalli", 8500000, 1180),
        ],
        "hyderabad": [
            ("Gachibowli", 9500000, 1250),
            ("Madhapur", 8700000, 1150),
            ("Kondapur", 8900000, 1220),
            ("Banjara Hills", 14500000, 1600),
            ("Manikonda", 8200000, 1100),
            ("Kukatpally", 7600000, 1050),
            ("HiTech City", 13800000, 1550),
            ("Miyapur", 7200000, 980),
            ("Tellapur", 8800000, 1200),
            ("Nallagandla", 9000000, 1180),
        ],
        "pune": [
            ("Hinjewadi", 8500000, 1200),
            ("Baner", 9200000, 1300),
            ("Wakad", 8700000, 1180),
            ("Kharadi", 9700000, 1350),
            ("Hadapsar", 7800000, 1100),
            ("Magarpatta", 9900000, 1400),
            ("Aundh", 10500000, 1450),
            ("Viman Nagar", 11200000, 1500),
            ("Kothrud", 9500000, 1380),
            ("Balewadi", 8800000, 1250),
        ],
        "chennai": [
            ("Velachery", 8500000, 1200),
            ("T Nagar", 11500000, 1450),
            ("Anna Nagar", 11200000, 1420),
            ("Porur", 7800000, 1100),
            ("Tambaram", 7300000, 950),
            ("Adyar", 11800000, 1550),
            ("Sholinganallur", 9000000, 1280),
            ("Guindy", 9700000, 1350),
            ("Ambattur", 7400000, 980),
            ("Nungambakkam", 12500000, 1600),
        ],
    }

    # Detect which city to use
    city = "bangalore"
    for c in listings_data.keys():
        if c in query_lower:
            city = c
            break

    sample_listings = []
    for idx, (area, base_price, sqft) in enumerate(listings_data[city]):
        # Randomize prices a bit for realism
        random_price = base_price + random.randint(-500000, 500000)
        sample_listings.append({
            "id": f"{city[:2].upper()}-{idx+1}",
            "title": f"3BHK Apartment in {area}, {city.title()}",
            "price": random_price,
            "area": sqft,
            "bedrooms": random.choice([2, 3, 4]),
            "bathrooms": random.choice([2, 3]),
            "url": f"https://example.com/{city}/{area.replace(' ', '-').lower()}",
        })

    return sample_listings[:max_results]


def predict_listing_tool(area: float, bedrooms: int, bathrooms: int) -> Dict[str, Any]:
    """Predict property price using ML model."""
    if model is None:
        raise RuntimeError("ML model not loaded")

    features = np.array([[area, bedrooms, bathrooms]])
    pred_lakh = float(model.predict(features)[0])
    pred_inr = pred_lakh * 100000.0
    return {"predicted_price_inr": round(pred_inr, 2), "predicted_price_lakh": round(pred_lakh, 3)}


def get_history_tool(db: Session, limit: int = 5) -> List[Dict[str, Any]]:
    """Fetch prediction logs."""
    try:
        rows = db.execute(
            text("""
            SELECT id, area, bedrooms, bathrooms, predicted_price, created_at
            FROM prediction_logs
            ORDER BY id DESC
            LIMIT :limit
        """),
            {"limit": limit},
        ).fetchall()

        results = []
        for r in rows:
            rm = getattr(r, "_mapping", None)
            if rm:
                results.append({
                    "id": rm["id"],
                    "area": rm["area"],
                    "bedrooms": rm["bedrooms"],
                    "bathrooms": rm["bathrooms"],
                    "predicted_price": rm["predicted_price"],
                    "created_at": str(rm["created_at"]),
                })
            else:
                results.append({
                    "id": r[0],
                    "area": r[1],
                    "bedrooms": r[2],
                    "bathrooms": r[3],
                    "predicted_price": r[4],
                    "created_at": str(r[5]),
                })
        return results
    except Exception as e:
        LOGGER.warning(f"get_history_tool error: {e}")
        return []


def send_email_tool(to_email: str, subject: str, body: str) -> Dict[str, Any]:
    """Mock email sender."""
    LOGGER.info(f"Mock email: {to_email} | {subject}")
    return {"sent": True, "to": to_email, "subject": subject}


# ----------------------------------------------------------
# 🧠 Function definitions for OpenAI
# ----------------------------------------------------------
FUNCTIONS = [
    {
        "name": "search_listings",
        "description": "Search property listings given a user query",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "predict_listing",
        "description": "Predict property price using the trained ML model",
        "parameters": {
            "type": "object",
            "properties": {
                "area": {"type": "number"},
                "bedrooms": {"type": "integer"},
                "bathrooms": {"type": "integer"},
            },
            "required": ["area", "bedrooms", "bathrooms"],
        },
    },
    {
        "name": "get_history",
        "description": "Get recent prediction logs from DB",
        "parameters": {
            "type": "object",
            "properties": {"limit": {"type": "integer"}},
        },
    },
    {
        "name": "send_email",
        "description": "Send a mock summary email",
        "parameters": {
            "type": "object",
            "properties": {
                "to_email": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to_email", "subject", "body"],
        },
    },
]


# ----------------------------------------------------------
# 🤖 Main Agent Endpoint
# ----------------------------------------------------------
@router.post("/advise", response_model=AgentResponse)
def agent_advise(req: AgentRequest, db: Session = Depends(get_db)):
    """LLM-based property assistant with reasoning + tool use."""
    if client is None:
        raise HTTPException(status_code=500, detail="OpenAI client not initialized (missing API key)")

    system_prompt = (
        "You are an intelligent real estate advisor. You use tools such as property search, "
        "price prediction, and recent data analysis to assist users."
    )

    user_prompt = f"User goal: {req.goal}\nLocation: {req.location or 'N/A'}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        # Step 1: Ask model what to do
        completion = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=messages,
            functions=FUNCTIONS,
            function_call="auto",
            temperature=0.4,
            max_tokens=800,
        )

        choice = completion.choices[0].message

        if hasattr(choice, "function_call") and choice.function_call:
            func_call = choice.function_call
            func_name = func_call.name
            func_args = json.loads(func_call.arguments or "{}")
            LOGGER.info(f"LLM decided to call function: {func_name} with {func_args}")

            # Execute local function
            if func_name == "search_listings":
                result = {"listings": search_listings_tool(func_args.get("query", ""), func_args.get("max_results", req.max_listings))}
            elif func_name == "predict_listing":
                result = predict_listing_tool(
                    float(func_args["area"]), int(func_args["bedrooms"]), int(func_args["bathrooms"])
                )
            elif func_name == "get_history":
                result = {"history": get_history_tool(db, func_args.get("limit", 5))}
            elif func_name == "send_email":
                result = send_email_tool(func_args["to_email"], func_args["subject"], func_args["body"])
            else:
                result = {"error": f"Unknown function {func_name}"}

            # Step 2: Send results back for reasoning
            messages.append({"role": "function", "name": func_name, "content": json.dumps(result)})

            followup = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=messages,
                temperature=0.2,
                max_tokens=500,
            )

            final_text = followup.choices[0].message.content.strip()
            return {"advice": final_text, "actions": [{"function": func_name, "result": result}]}

        # If model didn’t call function — just reply
        return {"advice": choice.content.strip(), "actions": []}

    except Exception as e:
        LOGGER.exception("Agent error")
        raise HTTPException(status_code=500, detail=str(e))
