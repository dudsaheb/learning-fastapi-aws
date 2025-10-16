from datetime import timedelta, datetime, timezone
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from jose import jwt
from dotenv import load_dotenv
import os

from api.models import User, Image
from api.dependencies.deps import db_dependency, bcrypt_context

load_dotenv()

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

SECRET_KEY = os.getenv("AUTH_SECRET_KEY")
ALGORITHM = os.getenv("AUTH_ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = 20

MAX_BCRYPT_BYTES = 72  # bcrypt only supports passwords <= 72 bytes


# -----------------------------
# Schemas
# -----------------------------
class UserCreateRequest(BaseModel):
    username: str
    password: str
    first_name: str
    last_name: str
    image: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str
    image: Optional[str] = None


# -----------------------------
# Helpers
# -----------------------------
def authenticate_user(username: str, password: str, db):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None

    image = db.query(Image).filter(Image.user_id == user.id).first()
    user.image = image.image if image else None

    if not bcrypt_context.verify(password, user.hashed_password):
        return None
    return user


def create_access_token(username: str, user_id: int, expires_delta: timedelta):
    to_encode = {"sub": username, "id": user_id}
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# -----------------------------
# Routes
# -----------------------------
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(db: db_dependency, create_user_request: UserCreateRequest):
    # Validate password length for bcrypt
    if len(create_user_request.password.encode("utf-8")) > MAX_BCRYPT_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Password too long (max 72 characters). Please use a shorter password."
        )

    # Check for existing username
    existing_user = db.query(User).filter(User.username == create_user_request.username).first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Username already exists. Please choose a different username."
        )

    # Hash password safely
    hashed_password = bcrypt_context.hash(create_user_request.password[:MAX_BCRYPT_BYTES])

    # Create user
    create_user_model = User(
        username=create_user_request.username,
        first_name=create_user_request.first_name,
        last_name=create_user_request.last_name,
        hashed_password=hashed_password
    )
    db.add(create_user_model)
    db.commit()
    db.refresh(create_user_model)

    # Create optional image entry
    image_data = create_user_request.image if create_user_request.image else None
    image_model = Image(image=image_data, user_id=create_user_model.id)
    db.add(image_model)
    db.commit()

    return {"message": "User created successfully", "username": create_user_model.username}


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: db_dependency
):
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(user.username, user.id, access_token_expires)

    return {"access_token": token, "token_type": "bearer", "image": user.image}
