from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from datetime import datetime, timezone
import random

from .routers import dogs, comments, posts, auth
# pay, payments, consumer
from .routers import payments
from .models import Dog, Comment, Post, Image, User, SessionLocal
from .load_test import router as load_test_router
#from .load_test_ui import router as load_test_ui_router
from api.payments_api import router as payments_router

from fastapi.responses import RedirectResponse
from fastapi.requests import Request
from fastapi import Request
import traceback
from fastapi.responses import JSONResponse
import sys


load_dotenv()

app = FastAPI()
# #allow_origins=[os.getenv("API_URL")],  # The default React port
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # The default React port
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


# -------------------------------------------------------------------
# CORSMiddleware should be FIRST and configured before routers
# -------------------------------------------------------------------
# Recommended: explicitly list your frontend origins for production
allowed_origins = [
    "https://frontendreact.sdude.in",
    "https://sdude.in",
    "https://main.d1d1negibjx492.amplifyapp.com",
    "http://localhost:3000",  # for local testing
    "http://localhost:8000",  # for local testing
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # use ["*"] only for debugging
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# ✅ Custom HTTPS redirect middleware
# (handles HTTP→HTTPS safely without breaking OPTIONS preflight)
# -------------------------------------------------------------------
@app.middleware("http")
async def conditional_https_redirect(request: Request, call_next):
    # Skip redirect for preflight requests and when already HTTPS
    if request.url.scheme == "http" and request.method != "OPTIONS":
        url = request.url.replace(scheme="https")
        return RedirectResponse(url=url._url)
    return await call_next(request)






@app.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        # Print full stack trace to console / Elastic Beanstalk logs
        print(f"\n--- Exception in request: {request.method} {request.url} ---", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        print(f"--- End of exception ---\n", file=sys.stderr)
        
        # Return a safe JSON error to the client
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


@app.post("/populate/")
def populate_db():
    session = SessionLocal()
    try:
        # Insert Users
        users = [User(username=f'user{i}', hashed_password=f'hash{i}', first_name=f'First{i}', last_name=f'Last{i}') for i in range(1, 31)]
        session.add_all(users)
        session.commit()

        # Refresh each user instance if necessary
        for user in users:
            session.refresh(user)

        # Insert Dogs, Posts, Comments, and Images
        for user in users:
            dogs = [Dog(name=f'Dog{j}', breed=f'Breed{j%5}', age=random.randint(1, 10), user_id=user.id) for j in range(1, 6)]
            session.add_all(dogs)
            
            posts = [Post(content=f'Content{k}', timestamp=datetime.now(timezone.utc), user_id=user.id) for k in range(1, 11)]
            session.add_all(posts)

            # Insert an Image record with image set to None
            image = Image(image=None, user_id=user.id)
            session.add(image)
        
        session.commit()

        # Collect all posts to randomly assign comments
        all_posts = session.query(Post).all()
        for user in users:
            selected_posts = random.sample(all_posts, 4)
            for post in selected_posts:
                comment = Comment(content=f'Comment from user {user.id} on post {post.id}', timestamp=datetime.now(timezone.utc), user_id=user.id, post_id=post.id)
                session.add(comment)

        session.commit()
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
    return {"message": "Database populated successfully!"}

# -------------------------------------------------------------------
# Include routers
# -------------------------------------------------------------------
app.include_router(auth.router)
app.include_router(dogs.router)
app.include_router(comments.router)
app.include_router(posts.router)
app.include_router(payments.router)
app.include_router(load_test_router)
app.include_router(payments_router)

@app.get("/")
async def health_check():
    return {"Healthy": 200}

@app.get("/health")
async def health():
    return {"status": "ok"}


#comment