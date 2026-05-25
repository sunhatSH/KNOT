"""Async repository classes for KNOT persistence.

Each repository bridges Pydantic domain models and SQLAlchemy ORM models.
Methods accept an AsyncSession for dependency-injection-friendly usage.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from knot.core.models import (
    Agent,
    ConversationSession,
    ConversationTurn,
    Edge,
    Execution,
    KnowledgeBase,
    Node,
    NodeStatus,
    User,
    Workflow,
    WorkflowStatus,
)
from knot.core.orm_models import (
    AgentModel,
    ConversationSessionModel,
    ExecutionModel,
    KnowledgeBaseModel,
    UserModel,
    WorkflowModel,
)

# ─── Serialisation helpers ──────────────────────────────────────────────────


def _workflow_to_orm(workflow: Workflow) -> WorkflowModel:
    """Convert a Pydantic Workflow to an ORM WorkflowModel."""
    return WorkflowModel(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        nodes_json=[n.model_dump() for n in workflow.nodes],
        edges_json=[e.model_dump() for e in workflow.edges],
        global_context_json=workflow.global_context,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        tags_json=workflow.tags,
    )


def _workflow_from_orm(model: WorkflowModel) -> Workflow:
    """Convert an ORM WorkflowModel back to a Pydantic Workflow."""
    return Workflow(
        id=model.id,
        name=model.name,
        description=model.description,
        nodes=[Node(**n) for n in (model.nodes_json or [])],
        edges=[Edge(**e) for e in (model.edges_json or [])],
        global_context=model.global_context_json or {},
        created_at=model.created_at,
        updated_at=model.updated_at,
        tags=model.tags_json or [],
    )


def _execution_to_orm(execution: Execution) -> ExecutionModel:
    """Convert a Pydantic Execution to an ORM ExecutionModel."""
    return ExecutionModel(
        id=execution.id,
        workflow_id=execution.workflow_id,
        status=execution.status.value,
        node_states_json={
            k: v.value for k, v in (execution.node_states or {}).items()
        },
        global_context_json=execution.global_context,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        error=execution.error,
        trace_json=execution.trace,
    )


def _execution_from_orm(model: ExecutionModel) -> Execution:
    """Convert an ORM ExecutionModel back to a Pydantic Execution."""
    return Execution(
        id=model.id,
        workflow_id=model.workflow_id,
        status=WorkflowStatus(model.status),
        node_states={
            k: NodeStatus(v) for k, v in (model.node_states_json or {}).items()
        },
        global_context=model.global_context_json or {},
        started_at=model.started_at,
        completed_at=model.completed_at,
        error=model.error,
        trace=model.trace_json or [],
    )


def _agent_to_orm(agent: Agent) -> AgentModel:
    """Convert a Pydantic Agent to an ORM AgentModel."""
    return AgentModel(
        id=agent.id,
        name=agent.name,
        role=agent.role.value,
        system_prompt=agent.system_prompt,
        model=agent.model,
        tools_json=agent.tools,
        config_json=agent.config,
    )


def _agent_from_orm(model: AgentModel) -> Agent:
    """Convert an ORM AgentModel back to a Pydantic Agent."""
    return Agent(
        id=model.id,
        name=model.name,
        role=model.role,  # AgentRole enum string; Pydantic coerces automatically
        system_prompt=model.system_prompt,
        model=model.model,
        tools=model.tools_json or [],
        config=model.config_json or {},
    )


def _kb_to_orm(kb: KnowledgeBase) -> KnowledgeBaseModel:
    """Convert a Pydantic KnowledgeBase to an ORM KnowledgeBaseModel."""
    return KnowledgeBaseModel(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        embedding_model=kb.embedding_model,
        collection_name=kb.collection_name,
        chunk_size=kb.chunk_size,
        chunk_overlap=kb.chunk_overlap,
    )


def _kb_from_orm(model: KnowledgeBaseModel) -> KnowledgeBase:
    """Convert an ORM KnowledgeBaseModel back to a Pydantic KnowledgeBase."""
    return KnowledgeBase(
        id=model.id,
        name=model.name,
        description=model.description,
        embedding_model=model.embedding_model,
        collection_name=model.collection_name,
        chunk_size=model.chunk_size,
        chunk_overlap=model.chunk_overlap,
    )


# ─── User helpers ────────────────────────────────────────────────────────────


def _user_from_orm(model: UserModel) -> User:
    """Convert an ORM UserModel back to a Pydantic User (no password hash)."""
    return User(
        id=model.id,
        username=model.username,
        email=model.email,
        role=model.role,  # UserRole enum; Pydantic coerces automatically
        is_active=model.is_active,
        created_at=model.created_at,
    )


# ─── Repositories ───────────────────────────────────────────────────────────


class WorkflowRepository:
    """Persistence operations for Workflow objects."""

    async def save(self, session: AsyncSession, workflow: Workflow) -> Workflow:
        """Persist a workflow (insert if new, update if existing)."""
        model = _workflow_to_orm(workflow)
        await session.merge(model)
        await session.commit()
        return workflow

    async def get(
        self, session: AsyncSession, workflow_id: str
    ) -> Workflow | None:
        """Retrieve a single workflow by ID."""
        model = await session.get(WorkflowModel, workflow_id)
        if model is None:
            return None
        return _workflow_from_orm(model)

    async def list(self, session: AsyncSession) -> list[Workflow]:
        """List all workflows."""
        result = await session.execute(
            select(WorkflowModel).order_by(WorkflowModel.created_at.desc())
        )
        models = result.scalars().all()
        return [_workflow_from_orm(m) for m in models]

    async def delete(
        self, session: AsyncSession, workflow_id: str
    ) -> bool:
        """Delete a workflow by ID. Returns True if deleted, False if not found."""
        model = await session.get(WorkflowModel, workflow_id)
        if model is None:
            return False
        await session.delete(model)
        await session.commit()
        return True

    async def search(
        self, session: AsyncSession, query: str
    ) -> list[Workflow]:
        """Search workflows by name or description (case-insensitive)."""
        stmt = select(WorkflowModel).where(
            WorkflowModel.name.ilike(f"%{query}%")
            | WorkflowModel.description.ilike(f"%{query}%")
        ).order_by(WorkflowModel.updated_at.desc())
        result = await session.execute(stmt)
        models = result.scalars().all()
        return [_workflow_from_orm(m) for m in models]


class ExecutionRepository:
    """Persistence operations for Execution objects."""

    async def save(
        self, session: AsyncSession, execution: Execution
    ) -> Execution:
        """Persist an execution (insert if new, update if existing)."""
        model = _execution_to_orm(execution)
        await session.merge(model)
        await session.commit()
        return execution

    async def get(
        self, session: AsyncSession, execution_id: str
    ) -> Execution | None:
        """Retrieve a single execution by ID."""
        model = await session.get(ExecutionModel, execution_id)
        if model is None:
            return None
        return _execution_from_orm(model)

    async def list_by_workflow(
        self, session: AsyncSession, workflow_id: str
    ) -> list[Execution]:
        """List all executions for a given workflow, newest first."""
        result = await session.execute(
            select(ExecutionModel)
            .where(ExecutionModel.workflow_id == workflow_id)
            .order_by(ExecutionModel.started_at.desc().nullslast())
        )
        models = result.scalars().all()
        return [_execution_from_orm(m) for m in models]


class AgentRepository:
    """Persistence operations for Agent objects."""

    async def save(self, session: AsyncSession, agent: Agent) -> Agent:
        """Persist an agent (insert if new, update if existing)."""
        model = _agent_to_orm(agent)
        await session.merge(model)
        await session.commit()
        return agent

    async def get(
        self, session: AsyncSession, agent_id: str
    ) -> Agent | None:
        """Retrieve a single agent by ID."""
        model = await session.get(AgentModel, agent_id)
        if model is None:
            return None
        return _agent_from_orm(model)

    async def list(self, session: AsyncSession) -> list[Agent]:
        """List all agents."""
        result = await session.execute(
            select(AgentModel).order_by(AgentModel.name)
        )
        models = result.scalars().all()
        return [_agent_from_orm(m) for m in models]

    async def get_by_role(
        self, session: AsyncSession, role: str
    ) -> list[Agent]:
        """List agents matching a given role (exact match on role string)."""
        result = await session.execute(
            select(AgentModel)
            .where(AgentModel.role == role)
            .order_by(AgentModel.name)
        )
        models = result.scalars().all()
        return [_agent_from_orm(m) for m in models]


class KnowledgeBaseRepository:
    """Persistence operations for KnowledgeBase objects."""

    async def save(
        self, session: AsyncSession, kb: KnowledgeBase
    ) -> KnowledgeBase:
        """Persist a knowledge base (insert if new, update if existing)."""
        model = _kb_to_orm(kb)
        await session.merge(model)
        await session.commit()
        return kb

    async def get(
        self, session: AsyncSession, kb_id: str
    ) -> KnowledgeBase | None:
        """Retrieve a single knowledge base by ID."""
        model = await session.get(KnowledgeBaseModel, kb_id)
        if model is None:
            return None
        return _kb_from_orm(model)

    async def list(self, session: AsyncSession) -> list[KnowledgeBase]:
        """List all knowledge bases."""
        result = await session.execute(
            select(KnowledgeBaseModel).order_by(
                KnowledgeBaseModel.created_at.desc()
            )
        )
        models = result.scalars().all()
        return [_kb_from_orm(m) for m in models]

    async def search(
        self, session: AsyncSession, query: str
    ) -> list[KnowledgeBase]:
        """Search knowledge bases by name or description (case-insensitive)."""
        stmt = select(KnowledgeBaseModel).where(
            KnowledgeBaseModel.name.ilike(f"%{query}%")
            | KnowledgeBaseModel.description.ilike(f"%{query}%")
        ).order_by(KnowledgeBaseModel.created_at.desc())
        result = await session.execute(stmt)
        models = result.scalars().all()
        return [_kb_from_orm(m) for m in models]


class UserRepository:
    """Persistence operations for User objects."""

    async def save(
        self, session: AsyncSession, user: User, password_hash: str
    ) -> User:
        """Persist a user with its password hash."""
        model = UserModel(
            id=user.id,
            username=user.username,
            email=user.email,
            password_hash=password_hash,
            role=user.role.value,
            is_active=user.is_active,
            created_at=user.created_at,
        )
        session.add(model)
        await session.commit()
        return user

    async def get(
        self, session: AsyncSession, user_id: str
    ) -> User | None:
        """Retrieve a single user by ID (no password hash returned)."""
        model = await session.get(UserModel, user_id)
        if model is None:
            return None
        return _user_from_orm(model)

    async def get_by_username(
        self, session: AsyncSession, username: str
    ) -> tuple[User, str] | None:
        """Retrieve a user by username, returning (User, password_hash)."""
        result = await session.execute(
            select(UserModel).where(UserModel.username == username)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _user_from_orm(model), model.password_hash

    async def list(self, session: AsyncSession) -> list[User]:
        """List all users (no password hashes returned)."""
        result = await session.execute(
            select(UserModel).order_by(UserModel.created_at.desc())
        )
        models = result.scalars().all()
        return [_user_from_orm(m) for m in models]


# ─── Conversation serialisation helpers ──────────────────────────────────────


def _conv_session_to_orm(session: ConversationSession) -> ConversationSessionModel:
    """Convert a Pydantic ConversationSession to an ORM ConversationSessionModel."""
    return ConversationSessionModel(
        id=session.id,
        workflow_id=session.workflow_id,
        execution_id=session.execution_id,
        turns_json=[t.model_dump() for t in session.turns],
        summary=session.summary,
        turn_count=session.turn_count,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _conv_session_from_orm(model: ConversationSessionModel) -> ConversationSession:
    """Convert an ORM ConversationSessionModel back to a Pydantic ConversationSession."""
    return ConversationSession(
        id=model.id,
        workflow_id=model.workflow_id,
        execution_id=model.execution_id,
        turns=[ConversationTurn(**t) for t in (model.turns_json or [])],
        summary=model.summary,
        turn_count=model.turn_count,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


# ─── Conversation Repository ─────────────────────────────────────────────


class ConversationRepository:
    """Persistence operations for ConversationSession objects."""

    async def save(
        self, session: AsyncSession, conv: ConversationSession
    ) -> ConversationSession:
        """Persist a conversation session (insert if new, update if existing)."""
        model = _conv_session_to_orm(conv)
        await session.merge(model)
        await session.commit()
        return conv

    async def get(
        self, session: AsyncSession, conv_id: str
    ) -> ConversationSession | None:
        """Retrieve a single conversation session by ID."""
        model = await session.get(ConversationSessionModel, conv_id)
        if model is None:
            return None
        return _conv_session_from_orm(model)

    async def list(self, session: AsyncSession) -> list[ConversationSession]:
        """List all conversation sessions, most recently updated first."""
        result = await session.execute(
            select(ConversationSessionModel).order_by(
                ConversationSessionModel.updated_at.desc()
            )
        )
        models = result.scalars().all()
        return [_conv_session_from_orm(m) for m in models]

    async def delete(
        self, session: AsyncSession, conv_id: str
    ) -> bool:
        """Delete a conversation session by ID. Returns True if deleted, False if not found."""
        model = await session.get(ConversationSessionModel, conv_id)
        if model is None:
            return False
        await session.delete(model)
        await session.commit()
        return True
