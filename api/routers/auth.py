from datetime import timedelta, datetime, timezone
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from jose import jwt
from dotenv import load_dotenv
import os, sys, hashlib

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
# Helper Functions
# -----------------------------
def safe_hash_password(password: str) -> str:
    """Try bcrypt; fallback to SHA256 if bcrypt fails."""
    try:
        # bcrypt only uses the first 72 bytes internally
        return bcrypt_context.hash(password[:72])
    except Exception as e:
        print(f"[WARN] bcrypt failed: {e}", file=sys.stderr)
        # fallback: SHA256 hashing (not for prod, but fine for assignment)
        sha256_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return sha256_hash


def verify_password(password: str, hashed: str) -> bool:
    """Verify bcrypt or SHA256 fallback."""
    try:
        return bcrypt_context.verify(password[:72], hashed)
    except Exception:
        # fallback to SHA256 check
        sha256_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return sha256_hash == hashed


def authenticate_user(username: str, password: str, db):
    """Authenticate a user by username and password."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None

    image = db.query(Image).filter(Image.user_id == user.id).first()
    user.image = image.image if image else None

    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(username: str, user_id: int, expires_delta: timedelta):
    """Generate JWT access token."""
    payload = {"sub": username, "id": user_id}
    expire = datetime.now(timezone.utc) + expires_delta
    payload.update({"exp": expire})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# -----------------------------
# Routes
# -----------------------------
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(db: db_dependency, create_user_request: UserCreateRequest):
    """Create a new user safely."""
    existing_user = db.query(User).filter(User.username == create_user_request.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    hashed_password = safe_hash_password(create_user_request.password)

    new_user = User(
        username=create_user_request.username,
        first_name=create_user_request.first_name,
        last_name=create_user_request.last_name,
        hashed_password=hashed_password,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    image_data = create_user_request.image if create_user_request.image else None
    image_model = Image(image=image_data, user_id=new_user.id)
    db.add(image_model)
    db.commit()

    print(f"✅ User created successfully: {new_user.username}", file=sys.stderr)
    return {"message": "User created successfully", "username": new_user.username}


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: db_dependency
):
    """Login and issue JWT token."""
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(user.username, user.id, access_token_expires)

    return {"access_token": token, "token_type": "bearer", "image": user.image}
