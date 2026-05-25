"""KNOT CLI — command-line interface for workflow management."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="knot",
        description="KNOT — Knowledge-enhanced task Orchestration for LLM Tuning",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # knot run
    run_parser = subparsers.add_parser("run", help="Run a workflow")
    run_parser.add_argument("workflow_file", help="Path to workflow JSON file")
    run_parser.add_argument("--context", "-c", help="JSON context for the workflow")

    # knot serve
    serve_parser = subparsers.add_parser("serve", help="Start the API server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    serve_parser.add_argument("--port", "-p", type=int, default=8000, help="Port to listen on")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    # knot workflow
    wf_parser = subparsers.add_parser("workflow", help="Workflow management")
    wf_sub = wf_parser.add_subparsers(dest="wf_command")
    wf_sub.add_parser("list", help="List workflows")

    return parser


async def cmd_run(args: argparse.Namespace) -> None:
    """Execute a workflow from a JSON file."""
    from knot.api.app import create_app

    app = create_app()
    engine = app.state  # Will be refactored when DB is added

    with open(args.workflow_file) as f:
        data = json.load(f)

    from knot.core.models import Workflow

    workflow = Workflow(**data)
    context = json.loads(args.context) if args.context else {}

    # Need to access engine from app — for CLI we create one directly
    from knot.execution_layer.registry import tool_registry
    from knot.execution_layer.tool_executor import CalculatorTool, EchoTool, HTTPRequestTool
    from knot.knowledge_layer.enhancer import ContextEnhancer
    from knot.knowledge_layer.retriever import HybridRetriever
    from knot.llm import ProviderRegistry
    from knot.llm.registry import init_default_providers
    from knot.orchestration_layer.scheduler import AgentScheduler
    from knot.orchestration_layer.workflow import WorkflowEngine

    init_default_providers()
    registry = ProviderRegistry()
    llm = registry.get()

    scheduler = AgentScheduler()
    retriever = HybridRetriever(registry)
    enhancer = ContextEnhancer()

    tool_registry.register(EchoTool())
    tool_registry.register(CalculatorTool())
    tool_registry.register(HTTPRequestTool())

    engine = WorkflowEngine(
        llm_provider=llm,
        scheduler=scheduler,
        retriever=retriever,
        enhancer=enhancer,
    )

    workflow.global_context.update(context)
    execution = await engine.execute(workflow)
    print(json.dumps(execution.model_dump(), indent=2, default=str))


def cmd_serve(args: argparse.Namespace) -> None:
    """Start the API server."""
    import uvicorn
    from knot.api.app import create_app

    app = create_app()
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


async def cmd_workflow(args: argparse.Namespace) -> None:
    """Workflow management commands."""
    if args.wf_command == "list":
        print("Workflow list (not yet implemented with DB)")


async def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run":
        await cmd_run(args)
    elif args.command == "serve":
        cmd_serve(args)
    elif args.command == "workflow":
        await cmd_workflow(args)
    else:
        parser.print_help()
        sys.exit(1)


def app() -> None:
    """Entry point for pyproject.toml scripts."""
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
