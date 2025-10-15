from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from datetime import datetime, timezone
import random

from .routers import dogs, comments, posts, auth, payments
from .models import Dog, Comment, Post, Image, User, SessionLocal

import boto3
import json


load_dotenv()

app = FastAPI()


# ====== Adding aws SQS code =======

# Set Queue URL from env variable
QUEUE_URL = os.getenv("SQS_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/284077270042/PaymentsQueue")

# Create SQS client
sqs = boto3.client('sqs', region_name='us-east-1')

@app.post("/payments/")
async def create_payment(payment: dict):
    try:
        # Send payment to SQS
        response = sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps(payment)
        )
        return {"status": "queued", "message_id": response['MessageId']}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ======= End aws SQS code ========

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("API_URL")],  # The default React port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

app.include_router(auth.router)
app.include_router(dogs.router)
app.include_router(comments.router)
app.include_router(posts.router)

app.include_router(payments.router)

@app.get("/")
async def health_check():
    return {"Healthy": 200}