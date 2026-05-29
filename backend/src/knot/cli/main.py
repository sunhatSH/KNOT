"""KNOT CLI — command-line interface for workflow management."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys


# ─── Version ────────────────────────────────────────────────────────────────


def _get_version() -> str:
    try:
        from knot import __version__
        return __version__
    except ImportError:
        return "unknown"


# ─── Argparse builder ───────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="knot",
        description="KNOT — Knowledge-enhanced task Orchestration for LLM Tuning",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {_get_version()}"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output results as JSON"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── serve ────────────────────────────────────────────────────────────
    p_serve = subparsers.add_parser("serve", help="Start the API server")
    p_serve.add_argument("--host", default="0.0.0.0", help="Host to bind")
    p_serve.add_argument("--port", "-p", type=int, default=8000, help="Port to listen on")
    p_serve.add_argument("--reload", action="store_true", help="Enable auto-reload")

    # ── init ─────────────────────────────────────────────────────────────
    subparsers.add_parser("init", help="Initialize database tables")

    # ── workflow ─────────────────────────────────────────────────────────
    p_wf = subparsers.add_parser("workflow", help="Workflow management")
    wf_sub = p_wf.add_subparsers(dest="wf_command", help="Workflow commands")

    p_wf_list = wf_sub.add_parser("list", help="List all workflows")
    p_wf_list.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    p_wf_run = wf_sub.add_parser("run", help="Execute a workflow by ID")
    p_wf_run.add_argument("workflow_id", help="Workflow ID to execute")
    p_wf_run.add_argument("--context", "-c", help="JSON context string for the workflow")

    p_wf_status = wf_sub.add_parser("status", help="Check execution status")
    p_wf_status.add_argument("execution_id", help="Execution ID to check")

    # ── knowledge ────────────────────────────────────────────────────────
    p_kb = subparsers.add_parser("knowledge", help="Knowledge base management")
    kb_sub = p_kb.add_subparsers(dest="kb_command", help="Knowledge commands")

    kb_sub.add_parser("list", help="List knowledge collections")

    p_kb_search = kb_sub.add_parser("search", help="Search knowledge base")
    p_kb_search.add_argument("collection", help="Collection name to search")
    p_kb_search.add_argument("query", help="Search query")
    p_kb_search.add_argument("--top-k", type=int, default=5, help="Number of results (default: 5)")

    # ── tools ────────────────────────────────────────────────────────────
    p_tools = subparsers.add_parser("tools", help="Tool management")
    tools_sub = p_tools.add_subparsers(dest="tools_command", help="Tool commands")

    tools_sub.add_parser("list", help="List available tools")

    p_tool_run = tools_sub.add_parser("run", help="Run a tool")
    p_tool_run.add_argument("tool_name", help="Tool name to execute")
    p_tool_run.add_argument("params", help="JSON parameters for the tool")

    return parser


# ─── Helper: print table ────────────────────────────────────────────────────


def _print_table(rows: list[list[str]], headers: list[str]) -> None:
    """Print a simple aligned table."""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
    sep = "  ".join("-" * w for w in col_widths)

    print(fmt.format(*headers))
    print(sep)
    for row in rows:
        print(fmt.format(*row))


def _maybe_json(data, *, force: bool = False) -> None:
    """Print JSON output if --json flag is set."""
    print(json.dumps(data, indent=2, default=str))


def _make_session():
    """Return an async database session context manager."""
    from knot.core.database import session_factory
    return session_factory()


# ─── Command: serve ─────────────────────────────────────────────────────────


def _cmd_serve(args: argparse.Namespace) -> None:
    """Start the FastAPI server."""
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is required. Install it with: pip install uvicorn[standard]")
        sys.exit(1)

    try:
        from knot.api.app import create_app
        app = create_app()
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)


# ─── Command: init ──────────────────────────────────────────────────────────


async def _cmd_init(args: argparse.Namespace) -> None:
    """Initialize database tables."""
    try:
        from knot.core.database import init_db
        print("Initializing database tables...")
        await init_db()
        print("Database tables created successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")
        sys.exit(1)


# ─── Command: workflow list ─────────────────────────────────────────────────


async def _cmd_workflow_list(args: argparse.Namespace) -> None:
    """List all workflows."""
    try:
        from knot.core.repository import WorkflowRepository

        repo = WorkflowRepository()
        async with _make_session() as session:
            workflows = await repo.list(session)

        if not workflows:
            print("No workflows found.")
            return

        rows = [
            [wf.id, wf.name, wf.description[:60] if wf.description else "",
             str(wf.created_at)[:19]]
            for wf in workflows
        ]
        _print_table(rows, ["ID", "Name", "Description", "Created At"])
    except Exception as e:
        print(f"Error listing workflows: {e}")
        sys.exit(1)


# ─── Command: workflow run ──────────────────────────────────────────────────


async def _cmd_workflow_run(args: argparse.Namespace) -> None:
    """Execute a workflow by ID."""
    try:
        from knot.core.repository import WorkflowRepository

        # Load workflow from database
        repo = WorkflowRepository()
        async with _make_session() as session:
            workflow = await repo.get(session, args.workflow_id)

        if workflow is None:
            print(f"Error: Workflow '{args.workflow_id}' not found.")
            sys.exit(1)

        # Parse optional context
        context_override = {}
        if args.context:
            try:
                context_override = json.loads(args.context)
            except json.JSONDecodeError as e:
                print(f"Error: Invalid JSON context: {e}")
                sys.exit(1)

        workflow.global_context.update(context_override)

        # Initialize runtime components
        from knot.llm.registry import init_default_providers, registry as llm_registry
        from knot.orchestration_layer.scheduler import AgentScheduler
        from knot.orchestration_layer.workflow import WorkflowEngine
        from knot.knowledge_layer.retriever import HybridRetriever
        from knot.knowledge_layer.enhancer import ContextEnhancer

        init_default_providers()
        llm = llm_registry.get()
        scheduler = AgentScheduler()
        scheduler.register_default_agents()
        retriever = HybridRetriever(llm_registry)
        enhancer = ContextEnhancer()

        engine = WorkflowEngine(
            llm_provider=llm,
            scheduler=scheduler,
            retriever=retriever,
            enhancer=enhancer,
        )

        print(f"Executing workflow '{workflow.name}' ({workflow.id})...")
        execution = await engine.execute(workflow)

        print(f"\nExecution ID: {execution.id}")
        print(f"Status: {execution.status.value}")
        if execution.error:
            print(f"Error: {execution.error}")
        if execution.completed_at and execution.started_at:
            duration = execution.completed_at - execution.started_at
            print(f"Duration: {duration.total_seconds():.2f}s")

        if execution.node_states:
            print("\nNode states:")
            rows = [[nid, status.value] for nid, status in execution.node_states.items()]
            _print_table(rows, ["Node", "Status"])

    except Exception as e:
        print(f"Error running workflow: {e}")
        sys.exit(1)


# ─── Command: workflow status ───────────────────────────────────────────────


async def _cmd_workflow_status(args: argparse.Namespace) -> None:
    """Check execution status."""
    try:
        from knot.core.repository import ExecutionRepository

        repo = ExecutionRepository()
        async with _make_session() as session:
            execution = await repo.get(session, args.execution_id)

        if execution is None:
            print(f"Error: Execution '{args.execution_id}' not found.")
            sys.exit(1)

        print(f"Execution ID: {execution.id}")
        print(f"Workflow ID: {execution.workflow_id}")
        print(f"Status: {execution.status.value}")
        if execution.error:
            print(f"Error: {execution.error}")
        if execution.started_at:
            started = execution.started_at.strftime("%Y-%m-%d %H:%M:%S")
            print(f"Started at: {started}")
        if execution.completed_at:
            completed = execution.completed_at.strftime("%Y-%m-%d %H:%M:%S")
            print(f"Completed at: {completed}")
        if execution.started_at and execution.completed_at:
            duration = execution.completed_at - execution.started_at
            print(f"Duration: {duration.total_seconds():.2f}s")

        if execution.node_states:
            print("\nNode states:")
            rows = [[nid, status.value] for nid, status in execution.node_states.items()]
            _print_table(rows, ["Node", "Status"])

    except Exception as e:
        print(f"Error checking execution status: {e}")
        sys.exit(1)


# ─── Command: knowledge list ────────────────────────────────────────────────


async def _cmd_knowledge_list(args: argparse.Namespace) -> None:
    """List knowledge collections."""
    try:
        from knot.core.repository import KnowledgeBaseRepository

        repo = KnowledgeBaseRepository()
        async with _make_session() as session:
            collections = await repo.list(session)

        if not collections:
            print("No knowledge collections found.")
            return

        rows = [
            [kb.id, kb.name, kb.description[:60] if kb.description else "",
             kb.collection_name or "", kb.embedding_model]
            for kb in collections
        ]
        _print_table(rows, ["ID", "Name", "Description", "Collection", "Embedding"])
    except Exception as e:
        print(f"Error listing knowledge collections: {e}")
        sys.exit(1)


# ─── Command: knowledge search ──────────────────────────────────────────────


async def _cmd_knowledge_search(args: argparse.Namespace) -> None:
    """Search knowledge base."""
    try:
        from knot.llm.registry import init_default_providers, registry as llm_registry
        from knot.knowledge_layer.retriever import HybridRetriever

        init_default_providers()
        retriever = HybridRetriever(llm_registry)

        print(f"Searching collection '{args.collection}' for: {args.query}")
        results = await retriever.retrieve(
            collection_name=args.collection,
            query=args.query,
            top_k=args.top_k,
        )

        if not results:
            print("No results found.")
            return

        print(f"\nTop {len(results)} results:")
        for i, chunk in enumerate(results, 1):
            print(f"\n--- Result {i} (score: {chunk.score:.4f}) ---")
            print(f"  ID: {chunk.id}")
            print(f"  Content: {chunk.content[:200]}{'...' if len(chunk.content) > 200 else ''}")
            if chunk.document_id:
                print(f"  Document: {chunk.document_id}")

    except Exception as e:
        print(f"Error searching knowledge base: {e}")
        sys.exit(1)


# ─── Command: tools list ────────────────────────────────────────────────────


def _cmd_tools_list(args: argparse.Namespace) -> None:
    """List available tools."""
    try:
        from knot.execution_layer.tool_executor import (
            CalculatorTool,
            EchoTool,
        )
        from knot.execution_layer.registry import tool_registry

        # Register default tools for CLI usage
        tool_registry.register(EchoTool())
        tool_registry.register(CalculatorTool())

        tools = tool_registry.list_tools()
        if not tools:
            print("No tools registered.")
            return

        rows = [
            [t["name"], t.get("description", "")[:80]]
            for t in tools
        ]
        _print_table(rows, ["Name", "Description"])
    except Exception as e:
        print(f"Error listing tools: {e}")
        sys.exit(1)


# ─── Command: tools run ─────────────────────────────────────────────────────


async def _cmd_tools_run(args: argparse.Namespace) -> None:
    """Run a tool with JSON params."""
    try:
        from knot.execution_layer.tool_executor import (
            CalculatorTool,
            EchoTool,
        )
        from knot.execution_layer.registry import tool_registry

        # Register default tools for CLI usage
        tool_registry.register(EchoTool())
        tool_registry.register(CalculatorTool())

        try:
            params = json.loads(args.params)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON params: {e}")
            sys.exit(1)

        result = await tool_registry.execute(args.tool_name, params)
        if result.success:
            print(json.dumps(result.output, indent=2, default=str))
        else:
            print(f"Error: {result.error}")
            sys.exit(1)

    except Exception as e:
        print(f"Error running tool: {e}")
        sys.exit(1)


# ─── Main dispatcher ────────────────────────────────────────────────────────


async def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "serve":
            _cmd_serve(args)
        elif args.command == "init":
            await _cmd_init(args)
        elif args.command == "workflow":
            if args.wf_command == "list":
                await _cmd_workflow_list(args)
            elif args.wf_command == "run":
                await _cmd_workflow_run(args)
            elif args.wf_command == "status":
                await _cmd_workflow_status(args)
            else:
                print("Error: unknown workflow command. Use: list, run, status")
                sys.exit(1)
        elif args.command == "knowledge":
            if args.kb_command == "list":
                await _cmd_knowledge_list(args)
            elif args.kb_command == "search":
                await _cmd_knowledge_search(args)
            else:
                print("Error: unknown knowledge command. Use: list, search")
                sys.exit(1)
        elif args.command == "tools":
            if args.tools_command == "list":
                _cmd_tools_list(args)
            elif args.tools_command == "run":
                await _cmd_tools_run(args)
            else:
                print("Error: unknown tools command. Use: list, run")
                sys.exit(1)
        else:
            parser.print_help()
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)


def app() -> None:
    """Entry point for pyproject.toml scripts directive."""
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
