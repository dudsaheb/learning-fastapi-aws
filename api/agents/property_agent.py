# api/agents/property_agent.py
"""
Agent router: accepts a user goal and uses OpenAI function-calling
to orchestrate tools:
 - search_listings (mock or real external API)
 - predict_listing (uses local ML model to predict price in INR)
 - get_history (reads recent predictions from DB)
 - send_email (mock; can integrate SES / SMTP later)

Requires environment:
 - OPENAI_API_KEY
 - PROPERTY_API_KEY (optional) if you wire a real listing API
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import openai
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

router = APIRouter(prefix="/agent", tags=["Agent"])

openai.api_key = os.getenv("OPENAI_API_KEY")
LOGGER = logging.getLogger("property_agent")
LOGGER.setLevel(logging.INFO)

# Load model for local predictions — same model used by /predict route
MODEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "model", "model.pkl"))
try:
    model = joblib.load(MODEL_PATH)
    LOGGER.info("Agent: model loaded")
except Exception as e:
    LOGGER.warning("Agent: model not loaded; predictions will fail if used. %s", e)
    model = None

# -----------------------------
# Request / Response Schemas
# -----------------------------
class AgentRequest(BaseModel):
    goal: str
    max_listings: Optional[int] = 5
    location: Optional[str] = None


class AgentResponse(BaseModel):
    advice: str
    actions: list


# -----------------------------
# Helper: DB session dependency
# -----------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -----------------------------
# Tool implementations
# -----------------------------
def search_listings_tool(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Mock search listings tool. If you have a real property API,
    wire it here using PROPERTY_API_KEY env var.
    Returns list of dicts: {id, title, price (INR), area, bedrooms, bathrooms, url}
    """
    PROPERTY_API_KEY = os.getenv("PROPERTY_API_KEY")
    if PROPERTY_API_KEY:
        # Example template if you want to wire real API
        # resp = requests.get("https://api.example.com/search", params={"q": query, "limit": max_results}, headers={"Authorization": f"Bearer {PROPERTY_API_KEY}"})
        # return resp.json()["results"]
        pass

    # Mocked listings (use real data later)
    sample_listings = [
        {"id": "L1", "title": "3BHK in South Bangalore", "price": 8500000, "area": 1200, "bedrooms": 3, "bathrooms": 2, "url": "https://example/1"},
        {"id": "L2", "title": "2BHK near MG Road", "price": 7200000, "area": 950,  "bedrooms": 2, "bathrooms": 1, "url": "https://example/2"},
        {"id": "L3", "title": "4BHK independent house", "price": 16000000, "area": 2500, "bedrooms": 4, "bathrooms": 3, "url": "https://example/3"},
        {"id": "L4", "title": "3BHK apartment - outskirts", "price": 5500000, "area": 1400, "bedrooms": 3, "bathrooms": 2, "url": "https://example/4"},
        {"id": "L5", "title": "2BHK resale", "price": 4800000, "area": 800,  "bedrooms": 2, "bathrooms": 1, "url": "https://example/5"},
    ]
    return sample_listings[:max_results]


def predict_listing_tool(area: float, bedrooms: int, bathrooms: int) -> Dict[str, Any]:
    """
    Use the same regression model to predict price.
    Returns predicted_price (INR) and predicted_lakh for readability.
    """
    if model is None:
        raise RuntimeError("Model not loaded in agent")

    features = np.array([[area, bedrooms, bathrooms]])
    pred_lakh = float(model.predict(features)[0])
    pred_inr = pred_lakh * 100000.0
    return {"predicted_price_inr": round(pred_inr, 2), "predicted_price_lakh": round(pred_lakh, 3)}


def get_history_tool(db: Session, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Fetch recent prediction logs from DB.
    """
    try:
        rows = db.execute(text("""
            SELECT id, area, bedrooms, bathrooms, predicted_price, created_at
            FROM prediction_logs
            ORDER BY id DESC
            LIMIT :limit
        """), {"limit": limit}).fetchall()

        results = []
        for r in rows:
            rm = getattr(r, "_mapping", None)
            if rm:
                results.append({
                    "id": rm["id"], "area": rm["area"], "bedrooms": rm["bedrooms"],
                    "bathrooms": rm["bathrooms"], "predicted_price": rm["predicted_price"], "created_at": str(rm["created_at"])
                })
            else:
                results.append({
                    "id": r[0], "area": r[1], "bedrooms": r[2], "bathrooms": r[3], "predicted_price": r[4], "created_at": str(r[5])
                })
        return results
    except Exception as e:
        LOGGER.warning("get_history_tool error: %s", e)
        return []


def send_email_tool(to_email: str, subject: str, body: str) -> Dict[str, Any]:
    """
    Mock send email. Replace with AWS SES or SMTP integration in production.
    """
    LOGGER.info("send_email_tool: would send email to %s | subject=%s", to_email, subject)
    # Implement real email sender here. For now we return success.
    return {"sent": True, "to": to_email, "subject": subject}


# -----------------------------
# OpenAI function definitions for function-calling
# -----------------------------
FUNCTIONS = [
    {
        "name": "search_listings",
        "description": "Search property listings given a user query and return a list of listings",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search text or filter"},
                "max_results": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "predict_listing",
        "description": "Predict fair price for a listing using our ML model (area, bedrooms, bathrooms). Returns price in INR.",
        "parameters": {
            "type": "object",
            "properties": {
                "area": {"type": "number"},
                "bedrooms": {"type": "integer"},
                "bathrooms": {"type": "integer"}
            },
            "required": ["area", "bedrooms", "bathrooms"],
        },
    },
    {
        "name": "get_history",
        "description": "Return recent prediction history from DB.",
        "parameters": {
            "type": "object",
            "properties": {"limit": {"type": "integer"}},
        },
    },
    {
        "name": "send_email",
        "description": "Send a summary email to the user (mocked).",
        "parameters": {
            "type": "object",
            "properties": {
                "to_email": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"}
            },
            "required": ["to_email", "subject", "body"]
        }
    }
]


# -----------------------------
# Agent endpoint
# -----------------------------
@router.post("/advise", response_model=AgentResponse)
def agent_advise(req: AgentRequest, db: Session = Depends(get_db)):
    """
    Main entrypoint. Given a user's goal, the LLM will decide which tools to call,
    and the agent returns a final natural-language advice and a list of actions performed.
    """
    if not openai.api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    system_prompt = (
        "You are an autonomous property advisor assistant. Your job is to reach the user's goal "
        "by calling tools when necessary. Use the provided tools, and at the end produce a human-friendly "
        "summary and recommended actions."
    )

    user_prompt = f"Goal: {req.goal}\nLocation: {req.location or 'N/A'}\nReturn a clear decision and actionable recommendations."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        # First call: get model response, letting it call functions
        completion = openai.ChatCompletion.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=messages,
            functions=FUNCTIONS,
            function_call="auto",
            temperature=0.3,
            max_tokens=800,
        )

        choice = completion.choices[0]
        if choice.finish_reason == "function_call" or (choice.message and choice.message.get("function_call")):
            func_call = choice.message["function_call"]
            func_name = func_call["name"]
            func_args = json.loads(func_call.get("arguments") or "{}")
            LOGGER.info("LLM requested function: %s with args: %s", func_name, func_args)

            # Execute the requested function locally
            if func_name == "search_listings":
                listings = search_listings_tool(func_args.get("query", ""), func_args.get("max_results", req.max_listings))
                func_result = {"listings": listings}
            elif func_name == "predict_listing":
                pred = predict_listing_tool(float(func_args["area"]), int(func_args["bedrooms"]), int(func_args["bathrooms"]))
                func_result = pred
            elif func_name == "get_history":
                history = get_history_tool(db, limit=func_args.get("limit", 5))
                func_result = {"history": history}
            elif func_name == "send_email":
                sent = send_email_tool(func_args["to_email"], func_args["subject"], func_args["body"])
                func_result = sent
            else:
                func_result = {"error": f"Unknown function {func_name}"}

            # Send function result back to model for finalization
            messages.append(choice.message)  # the model's function_call
            messages.append({"role": "function", "name": func_name, "content": json.dumps(func_result)})

            followup = openai.ChatCompletion.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=messages,
                temperature=0.2,
                max_tokens=500,
            )

            final_text = followup.choices[0].message.get("content", "").strip()
            return {"advice": final_text, "actions": [{"function": func_name, "result": func_result}]}

        else:
            # Model didn't call a function — just return its text
            assistant_text = choice.message.get("content", "").strip()
            return {"advice": assistant_text, "actions": []}

    except Exception as e:
        LOGGER.exception("Agent error")
        raise HTTPException(status_code=500, detail=str(e))
