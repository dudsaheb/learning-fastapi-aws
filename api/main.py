from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from datetime import datetime, timezone
import random

from .routers import dogs, comments, posts, auth, payments
from .models import Dog, Comment, Post, Image, User, SessionLocal
import json
import boto3

load_dotenv()

app = FastAPI()





# ======= CORS Middleware =======
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("API_URL")],  # React front-end URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======= Include Routers =======
app.include_router(auth.router)
app.include_router(dogs.router)
app.include_router(comments.router)
app.include_router(posts.router)
app.include_router(payments.router)  # Payments router includes both DB and SQS endpoints

# ======= Health Check =======
@app.get("/")
async def health_check():
    return {"Healthy": 200}
