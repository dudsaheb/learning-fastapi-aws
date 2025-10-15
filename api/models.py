from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, validates
from datetime import datetime, timezone
from dotenv import load_dotenv
from sqlalchemy import Numeric, Text, func
import os

load_dotenv()

Base = declarative_base()

if os.getenv("DEPLOYMENT_ENVIRONMENT") == 'DEV':
    engine = create_engine(os.getenv("DB_URL"), connect_args={'check_same_thread': False})
else:
    engine = create_engine(os.getenv("DB_URL"))
    
#AWS_DATABASE_URL = "postgresql://rootuser:rootuser_password@fastapi-aws-database.cgx644u6a0rx.us-east-1.rds.amazonaws.com:5432/postgres"
#engine = create_engine(AWS_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    dogs = relationship("Dog", back_populates="owner")
    posts = relationship("Post", back_populates="user")
    images = relationship("Image", back_populates="owner", uselist=False)
    
class Image(Base):
    __tablename__ = 'images'
    id = Column(Integer, primary_key=True, index=True)
    image = Column(String)
    user_id = Column(Integer, ForeignKey('users.id'))
    owner = relationship("User", back_populates="images")

class Dog(Base):
    __tablename__ = 'dogs'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    breed = Column(String)
    age = Column(Integer)
    user_id = Column(Integer, ForeignKey('users.id'))
    owner = relationship("User", back_populates="dogs")

class Post(Base):
    __tablename__ = 'posts'
    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.now(timezone.utc))
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post", order_by="Comment.id")

class Comment(Base):
    __tablename__ = 'comments'
    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.now(timezone.utc))
    user_id = Column(Integer, ForeignKey('users.id'))
    post_id = Column(Integer, ForeignKey('posts.id'))
    user = relationship("User")
    post = relationship("Post", back_populates="comments")


class Payment(Base):
    __tablename__ = 'payments'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(8), nullable=False, default='INR')
    status = Column(String(32), nullable=False, default='PAID')  # e.g., PAID, FAILED, PENDING
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Optional: relationship to User if you want
    user = relationship("User", backref="payments")

Base.metadata.create_all(bind=engine)
