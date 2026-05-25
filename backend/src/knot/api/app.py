"""FastAPI application factory."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from knot.api.routes import agents as agent_routes
from knot.api.routes import knowledge as knowledge_routes
from knot.api.routes import workflows as workflow_routes
from knot.core.config import settings
from knot.execution_layer.registry import tool_registry
from knot.execution_layer.tool_executor import CalculatorTool, EchoTool, HTTPRequestTool
from knot.knowledge_layer.enhancer import ContextEnhancer
from knot.knowledge_layer.retriever import HybridRetriever
from knot.knowledge_layer.vector_store import vector_store
from knot.llm import ProviderRegistry
from knot.llm.registry import init_default_providers
from knot.orchestration_layer.scheduler import AgentScheduler
from knot.orchestration_layer.workflow import WorkflowEngine

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the KNOT FastAPI application."""
    app = FastAPI(
        title="KNOT API",
        description="Knowledge-enhanced task Orchestration for LLM Tuning",
        version="0.1.0",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize components
    init_default_providers()
    registry = ProviderRegistry()
    llm = registry.get()

    scheduler = AgentScheduler()
    retriever = HybridRetriever(registry)
    enhancer = ContextEnhancer()

    engine = WorkflowEngine(
        llm_provider=llm,
        scheduler=scheduler,
        retriever=retriever,
        enhancer=enhancer,
    )

    # Register default tools
    tool_registry.register(EchoTool())
    tool_registry.register(CalculatorTool())
    tool_registry.register(HTTPRequestTool())

    # Configure routes with dependencies
    workflow_routes.configure_routes(engine)
    agent_routes.configure_routes(scheduler)
    knowledge_routes.configure_routes(retriever)

    # Include routers
    app.include_router(workflow_routes.router)
    app.include_router(agent_routes.router)
    app.include_router(knowledge_routes.router)

    @app.on_event("startup")
    async def startup():
        """Initialize connections on startup."""
        try:
            await vector_store.connect()
            logger.info("Vector store connected")
        except Exception as e:
            logger.warning("Vector store connection failed (will retry): %s", e)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "version": "0.1.0"}

    logger.info("KNOT API initialized with provider: %s", llm.name)
    return app
