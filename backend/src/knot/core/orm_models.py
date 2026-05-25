"""SQLAlchemy ORM models for KNOT."""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from knot.core.database import Base


class WorkflowModel(Base):
    """ORM model for workflow definitions (maps to Pydantic Workflow)."""

    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    nodes_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    edges_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    global_context_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.now, onupdate=datetime.datetime.now
    )
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list)


class ExecutionModel(Base):
    """ORM model for workflow execution runs (maps to Pydantic Execution)."""

    __tablename__ = "executions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    node_states_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    global_context_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


class AgentModel(Base):
    """ORM model for AI agents (maps to Pydantic Agent)."""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="executor")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str] = mapped_column(String, nullable=False, default="deepseek-chat")
    tools_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class UserModel(Base):
    """ORM model for system users."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String, default="")
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, default="user")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.now
    )


class KnowledgeBaseModel(Base):
    """ORM model for knowledge-base collections (maps to Pydantic KnowledgeBase)."""

    __tablename__ = "knowledge_bases"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    embedding_model: Mapped[str] = mapped_column(
        String, nullable=False, default="deepseek-embedding"
    )
    collection_name: Mapped[str] = mapped_column(String, default="")
    chunk_size: Mapped[int] = mapped_column(Integer, default=512)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=64)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.now
    )


class ConversationSessionModel(Base):
    """ORM model for persisted conversation sessions."""

    __tablename__ = "conversation_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String, default="")
    execution_id: Mapped[str] = mapped_column(String, default="")
    turns_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.now, onupdate=datetime.datetime.now
    )
