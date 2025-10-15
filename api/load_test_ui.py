import asyncio
import aiohttp
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import os

router = APIRouter()
templates = Jinja2Templates(directory="api/templates")

apiUrl = os.getenv("API_URL")
endpoint = "/payments/"


@router.get("/loadtest", response_class=HTMLResponse)
async def loadtest_page(request: Request):
    """Display the load test UI page."""
    return templates.TemplateResponse("loadtest.html", {"request": request})


@router.get("/run-loadtest-ui")
async def run_loadtest_ui(count: int = 1000):
    """Trigger async load test and return summary JSON."""
    url = apiUrl+endpoint
    results = []

    async def send_payment(session, i):
        payload = {
            "user_id": i,
            "amount": 1,
            "currency": "INR",
            "description": f"load test {i}"
        }
        async with session.post(url, json=payload) as response:
            text = await response.text()
            return {"id": i, "status": response.status, "text": text}

    async with aiohttp.ClientSession() as session:
        tasks = [send_payment(session, i) for i in range(1, count + 1)]
        responses = await asyncio.gather(*tasks)

    success_count = sum(1 for r in responses if r["status"] == 200)
    fail_count = count - success_count

    return JSONResponse({
        "total_requests": count,
        "success": success_count,
        "failed": fail_count,
        "message": "Load test completed!"
    })
