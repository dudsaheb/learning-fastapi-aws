import asyncio
import aiohttp
import os
from fastapi import APIRouter

router = APIRouter()

apiUrl = os.getenv("API_URL")
endpoint = "/payments/"

@router.post("/run-loadtest/")
async def run_loadtest(count: int = 1000):
    """
    Fire 'count' POST requests to /payments endpoint for load testing.
    """

    url = apiUrl+endpoint  # Internal endpoint or EB domain

    async def send_payment(session, i):
        payload = {
            "user_id": i,
            "amount": 1,
            "currency": "INR",
            "description": f"load test {i}"
        }
        async with session.post(url, json=payload) as response:
            return await response.text()

    async with aiohttp.ClientSession() as session:
        tasks = [send_payment(session, i) for i in range(count)]
        await asyncio.gather(*tasks)

    return {"message": f"{count} requests sent successfully"}
