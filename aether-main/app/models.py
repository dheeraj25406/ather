from sqlalchemy import Column, String, DateTime, Text, Integer, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    session_metadata = Column(JSON, default={})


class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    role = Column(String, nullable=False)  # "user", "assistant", "system"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ToolCall(Base):
    __tablename__ = "tool_calls"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    tool_name = Column(String, nullable=False)
    arguments = Column(JSON, default={})
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Fact(Base):
    __tablename__ = "facts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    fact = Column(Text, nullable=False)
    embedding_id = Column(String, nullable=True)  # Reference to Qdrant point ID
    created_at = Column(DateTime, default=datetime.utcnow)
