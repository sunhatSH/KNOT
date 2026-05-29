"""FastAPI application factory."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from knot.api.middleware import RateLimitMiddleware
from knot.api.routes import agents as agent_routes
from knot.api.routes import auth as auth_routes
from knot.api.routes import knowledge as knowledge_routes
from knot.api.routes import templates as template_routes
from knot.api.routes import metrics as metrics_routes
from knot.api.routes import workflows as workflow_routes
from knot.api.routes import ws as ws_routes
from knot.api.routes.ws import ws_manager
from knot.core.config import settings
from knot.core.database import init_db
from knot.execution_layer.plugin import PluginLoader
from knot.execution_layer.registry import tool_registry
from knot.execution_layer.tool_executor import (
    CalculatorTool,
    DatabaseTool,
    EchoTool,
    HTTPRequestTool,
    ScriptTool,
)
from knot.knowledge_layer.enhancer import ContextEnhancer
from knot.knowledge_layer.retriever import HybridRetriever
from knot.knowledge_layer.vector_store import vector_store
from knot.llm.registry import init_default_providers, registry as llm_registry
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

    # Rate limiting
    app.add_middleware(RateLimitMiddleware)

    # Initialize components (uses global registry singleton)
    init_default_providers()
    llm = llm_registry.get()

    scheduler = AgentScheduler()
    # Register default multi-agent team
    scheduler.register_default_agents()
    logger.info("Registered %d default agents", len(scheduler.list_agents()))

    retriever = HybridRetriever(llm_registry)
    enhancer = ContextEnhancer()

    engine = WorkflowEngine(
        llm_provider=llm,
        scheduler=scheduler,
        retriever=retriever,
        enhancer=enhancer,
        broadcast_fn=ws_manager.broadcast,
    )

    # Register default tools
    tool_registry.register(EchoTool())
    tool_registry.register(CalculatorTool())
    tool_registry.register(HTTPRequestTool())
    tool_registry.register(DatabaseTool())
    tool_registry.register(ScriptTool())

    # Initialize plugin loader for external tools
    plugin_loader = PluginLoader(plugin_dirs=["plugins/"])

    # Configure routes with dependencies
    workflow_routes.configure_routes(engine, llm_provider=llm)
    agent_routes.configure_routes(scheduler)
    knowledge_routes.configure_routes(retriever)

    # Include routers
    app.include_router(workflow_routes.router)
    app.include_router(agent_routes.router)
    app.include_router(knowledge_routes.router)
    app.include_router(template_routes.router)
    app.include_router(auth_routes.router)
    app.include_router(ws_routes.router)
    app.include_router(metrics_routes.router)
    logger.info("JWT auth routes initialized at /api/v1/auth")

    @app.on_event("startup")
    async def startup():
        """Initialize connections on startup."""
        try:
            await init_db()
            logger.info("Database tables initialized")
        except Exception as e:
            logger.warning("Database initialization failed: %s", e)

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
