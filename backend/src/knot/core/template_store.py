"""File-based persistence for WorkflowTemplate objects.

Templates are stored as individual JSON files under ``backend/data/templates/``.
This avoids coupling the template system to the main database so that templates
can be pre-seeded and easily shared.

On instantiation the ``TemplateStore`` automatically scans the ``data/templates/``
directory and makes every ``*.json`` file available as a template — no registration
step required.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from knot.core.models import (
    Edge,
    Node,
    NodeStatus,
    Workflow,
    WorkflowTemplate,
)

TEMPLATES_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "templates"
)

# ── Built-in template definitions (used when the directory is empty) ──────
# These are written as JSON files during first-run so that users can edit or
# delete them freely.

_BUILTIN_TEMPLATES: list[dict] = [
    {
        "id": "data_analysis_pipeline",
        "name": "Data Analysis Pipeline",
        "description": "A complete data analysis workflow: fetch data from an API, analyze with LLM, and produce a structured report.",
        "category": "data",
        "tags": ["data", "analysis", "pipeline"],
        "nodes": [
            {
                "id": "n1", "type": "input", "label": "Input Parameters",
                "agent_id": None, "config": {"position": {"x": 250, "y": 0}},
                "inputs": {}, "outputs": {}, "condition": None,
                "retry_count": 0, "max_retries": 3, "timeout_seconds": 300,
                "status": "pending", "result": None, "error": None,
                "started_at": None, "completed_at": None,
            },
            {
                "id": "n2", "type": "task", "label": "Fetch Data from API",
                "agent_id": None, "config": {"position": {"x": 250, "y": 150}, "tool": "http_request", "method": "GET", "url": "https://api.example.com/data"},
                "inputs": {}, "outputs": {}, "condition": None,
                "retry_count": 0, "max_retries": 3, "timeout_seconds": 600,
                "status": "pending", "result": None, "error": None,
                "started_at": None, "completed_at": None,
            },
            {
                "id": "n3", "type": "task", "label": "Analyze with LLM",
                "agent_id": None, "config": {"position": {"x": 250, "y": 300}, "prompt": "Analyze the fetched data and provide key insights."},
                "inputs": {}, "outputs": {}, "condition": None,
                "retry_count": 0, "max_retries": 3, "timeout_seconds": 600,
                "status": "pending", "result": None, "error": None,
                "started_at": None, "completed_at": None,
            },
            {
                "id": "n4", "type": "output", "label": "Generate Report",
                "agent_id": None, "config": {"position": {"x": 250, "y": 450}},
                "inputs": {}, "outputs": {}, "condition": None,
                "retry_count": 0, "max_retries": 3, "timeout_seconds": 300,
                "status": "pending", "result": None, "error": None,
                "started_at": None, "completed_at": None,
            },
        ],
        "edges": [
            {"id": "e1", "source_id": "n1", "target_id": "n2", "label": ""},
            {"id": "e2", "source_id": "n2", "target_id": "n3", "label": ""},
            {"id": "e3", "source_id": "n3", "target_id": "n4", "label": ""},
        ],
        "config": {
            "default_api_url": "https://api.example.com/data",
            "analysis_model": "deepseek-chat",
            "output_format": "markdown",
        },
        "usage_count": 0,
        "created_at": "2025-01-01T00:00:00",
        "updated_at": "2025-01-01T00:00:00",
    },
    {
        "id": "customer_support",
        "name": "Customer Support Assistant",
        "description": "Handle customer inquiries: research using knowledge base, then generate a helpful response.",
        "category": "support",
        "tags": ["support", "knowledge", "rag"],
        "nodes": [
            {
                "id": "n1", "type": "input", "label": "Customer Inquiry",
                "agent_id": None, "config": {"position": {"x": 250, "y": 0}},
                "inputs": {}, "outputs": {}, "condition": None,
                "retry_count": 0, "max_retries": 3, "timeout_seconds": 300,
                "status": "pending", "result": None, "error": None,
                "started_at": None, "completed_at": None,
            },
            {
                "id": "n2", "type": "task", "label": "Research Knowledge Base",
                "agent_id": None, "config": {"position": {"x": 250, "y": 150}, "knowledge_enabled": True, "knowledge_collection": "support_docs", "top_k": 5},
                "inputs": {}, "outputs": {}, "condition": None,
                "retry_count": 0, "max_retries": 3, "timeout_seconds": 600,
                "status": "pending", "result": None, "error": None,
                "started_at": None, "completed_at": None,
            },
            {
                "id": "n3", "type": "output", "label": "Respond to Customer",
                "agent_id": None, "config": {"position": {"x": 250, "y": 300}},
                "inputs": {}, "outputs": {}, "condition": None,
                "retry_count": 0, "max_retries": 3, "timeout_seconds": 300,
                "status": "pending", "result": None, "error": None,
                "started_at": None, "completed_at": None,
            },
        ],
        "edges": [
            {"id": "e1", "source_id": "n1", "target_id": "n2", "label": ""},
            {"id": "e2", "source_id": "n2", "target_id": "n3", "label": ""},
        ],
        "config": {
            "knowledge_embedding_model": "deepseek-embedding",
            "max_context_chunks": 5,
            "response_tone": "professional",
        },
        "usage_count": 0,
        "created_at": "2025-01-01T00:00:00",
        "updated_at": "2025-01-01T00:00:00",
    },
    {
        "id": "multi_agent_debate",
        "name": "Multi-Agent Debate",
        "description": "Multiple AI agents debate a topic from different perspectives and converge on a consensus answer.",
        "category": "multi_agent",
        "tags": ["multi-agent", "debate", "collaboration"],
        "nodes": [
            {
                "id": "n1", "type": "input", "label": "Debate Topic",
                "agent_id": None, "config": {"position": {"x": 250, "y": 0}},
                "inputs": {}, "outputs": {}, "condition": None,
                "retry_count": 0, "max_retries": 3, "timeout_seconds": 300,
                "status": "pending", "result": None, "error": None,
                "started_at": None, "completed_at": None,
            },
            {
                "id": "n2", "type": "task", "label": "Agents Debate",
                "agent_id": None, "config": {"position": {"x": 250, "y": 150}, "multi_agent_mode": "debate", "agent_team": [{"agent_id": "agent_pro", "role": "researcher"}, {"agent_id": "agent_con", "role": "validator"}, {"agent_id": "agent_mod", "role": "summarizer"}], "max_rounds": 3},
                "inputs": {}, "outputs": {}, "condition": None,
                "retry_count": 0, "max_retries": 3, "timeout_seconds": 900,
                "status": "pending", "result": None, "error": None,
                "started_at": None, "completed_at": None,
            },
            {
                "id": "n3", "type": "output", "label": "Consensus Output",
                "agent_id": None, "config": {"position": {"x": 250, "y": 300}},
                "inputs": {}, "outputs": {}, "condition": None,
                "retry_count": 0, "max_retries": 3, "timeout_seconds": 300,
                "status": "pending", "result": None, "error": None,
                "started_at": None, "completed_at": None,
            },
        ],
        "edges": [
            {"id": "e1", "source_id": "n1", "target_id": "n2", "label": ""},
            {"id": "e2", "source_id": "n2", "target_id": "n3", "label": ""},
        ],
        "config": {
            "debate_rounds": 3,
            "consensus_threshold": 0.8,
            "agent_roles": ["researcher", "validator", "summarizer"],
        },
        "usage_count": 0,
        "created_at": "2025-01-01T00:00:00",
        "updated_at": "2025-01-01T00:00:00",
    },
    {
        "id": "etl_data_to_report",
        "name": "ETL Data to Report",
        "description": "Extract data from a database, transform it with a script, load into storage, and generate a report.",
        "category": "data",
        "tags": ["etl", "database", "report"],
        "nodes": [
            {
                "id": "n1", "type": "input", "label": "Job Configuration",
                "agent_id": None, "config": {"position": {"x": 250, "y": 0}},
                "inputs": {}, "outputs": {}, "condition": None,
                "retry_count": 0, "max_retries": 3, "timeout_seconds": 300,
                "status": "pending", "result": None, "error": None,
                "started_at": None, "completed_at": None,
            },
            {
                "id": "n2", "type": "task", "label": "Extract from Database",
                "agent_id": None, "config": {"position": {"x": 250, "y": 150}, "tool": "database_query", "query": "SELECT * FROM source_table WHERE processed = false", "connection_string_env": "DB_CONNECTION"},
                "inputs": {}, "outputs": {}, "condition": None,
                "retry_count": 0, "max_retries": 3, "timeout_seconds": 1200,
                "status": "pending", "result": None, "error": None,
                "started_at": None, "completed_at": None,
            },
            {
                "id": "n3", "type": "task", "label": "Transform Data",
                "agent_id": None, "config": {"position": {"x": 250, "y": 300}, "tool": "run_script", "script_language": "python", "script": "# Transform logic\nimport pandas as pd\n# data cleaning, normalization, enrichment"},
                "inputs": {}, "outputs": {}, "condition": None,
                "retry_count": 0, "max_retries": 3, "timeout_seconds": 900,
                "status": "pending", "result": None, "error": None,
                "started_at": None, "completed_at": None,
            },
            {
                "id": "n4", "type": "task", "label": "Load to Target",
                "agent_id": None, "config": {"position": {"x": 250, "y": 450}, "tool": "load", "target": "warehouse", "mode": "upsert"},
                "inputs": {}, "outputs": {}, "condition": None,
                "retry_count": 0, "max_retries": 3, "timeout_seconds": 1200,
                "status": "pending", "result": None, "error": None,
                "started_at": None, "completed_at": None,
            },
            {
                "id": "n5", "type": "output", "label": "Generate Report",
                "agent_id": None, "config": {"position": {"x": 250, "y": 600}},
                "inputs": {}, "outputs": {}, "condition": None,
                "retry_count": 0, "max_retries": 3, "timeout_seconds": 300,
                "status": "pending", "result": None, "error": None,
                "started_at": None, "completed_at": None,
            },
        ],
        "edges": [
            {"id": "e1", "source_id": "n1", "target_id": "n2", "label": ""},
            {"id": "e2", "source_id": "n2", "target_id": "n3", "label": ""},
            {"id": "e3", "source_id": "n3", "target_id": "n4", "label": ""},
            {"id": "e4", "source_id": "n4", "target_id": "n5", "label": ""},
        ],
        "config": {
            "batch_size": 5000,
            "source_db": "postgresql://localhost:5432/source",
            "target_warehouse": "s3://data-lake/processed/",
            "report_format": "html",
        },
        "usage_count": 0,
        "created_at": "2025-01-01T00:00:00",
        "updated_at": "2025-01-01T00:00:00",
    },
    {
        "id": "scheduled_health_monitor",
        "name": "Scheduled Health Monitor",
        "description": "Periodically check service health, analyze results, and send alerts on anomalies.",
        "category": "monitoring",
        "tags": ["monitoring", "alert", "health-check"],
        "nodes": [
            {
                "id": "n1", "type": "input", "label": "Monitor Config",
                "agent_id": None, "config": {"position": {"x": 250, "y": 0}},
                "inputs": {}, "outputs": {}, "condition": None,
                "retry_count": 0, "max_retries": 3, "timeout_seconds": 300,
                "status": "pending", "result": None, "error": None,
                "started_at": None, "completed_at": None,
            },
            {
                "id": "n2", "type": "task", "label": "Check Endpoint Health",
                "agent_id": None, "config": {"position": {"x": 250, "y": 150}, "tool": "http_request", "method": "GET", "url": "https://status.example.com/health", "expected_status": 200, "timeout": 30},
                "inputs": {}, "outputs": {}, "condition": None,
                "retry_count": 0, "max_retries": 3, "timeout_seconds": 300,
                "status": "pending", "result": None, "error": None,
                "started_at": None, "completed_at": None,
            },
            {
                "id": "n3", "type": "task", "label": "Analyze Health Status",
                "agent_id": None, "config": {"position": {"x": 250, "y": 300}, "condition_check": True, "alert_on": ["unhealthy", "degraded"], "metrics": ["response_time", "error_rate", "uptime"]},
                "inputs": {}, "outputs": {}, "condition": None,
                "retry_count": 0, "max_retries": 3, "timeout_seconds": 300,
                "status": "pending", "result": None, "error": None,
                "started_at": None, "completed_at": None,
            },
            {
                "id": "n4", "type": "output", "label": "Send Alert / Report",
                "agent_id": None, "config": {"position": {"x": 250, "y": 450}, "alert_channels": ["email", "slack", "webhook"]},
                "inputs": {}, "outputs": {}, "condition": None,
                "retry_count": 0, "max_retries": 5, "timeout_seconds": 120,
                "status": "pending", "result": None, "error": None,
                "started_at": None, "completed_at": None,
            },
        ],
        "edges": [
            {"id": "e1", "source_id": "n1", "target_id": "n2", "label": ""},
            {"id": "e2", "source_id": "n2", "target_id": "n3", "label": ""},
            {"id": "e3", "source_id": "n3", "target_id": "n4", "label": ""},
        ],
        "config": {
            "check_interval_seconds": 300,
            "alert_thresholds": {"response_time_ms": 2000, "error_rate_pct": 5},
            "notification_channels": ["email", "slack"],
        },
        "usage_count": 0,
        "created_at": "2025-01-01T00:00:00",
        "updated_at": "2025-01-01T00:00:00",
    },
]


class TemplateStore:
    """File-based CRUD for workflow templates.

    Templates are stored as individual JSON files under the configured
    directory (default: ``backend/data/templates/``).  The store auto-seeds
    built-in templates when the directory is first created or found empty.
    """

    def __init__(self, templates_dir: str | Path | None = None) -> None:
        self._dir = Path(templates_dir) if templates_dir else TEMPLATES_DIR
        self._init_directory()

    # ── initialisation ───────────────────────────────────────────────────

    def _init_directory(self) -> None:
        """Ensure the templates directory exists and seed built-ins if empty."""
        self._dir.mkdir(parents=True, exist_ok=True)

        # Seed default templates if the directory is empty (or only contains
        # non-JSON files).
        existing = list(self._dir.glob("*.json"))
        if not existing:
            for tpl_dict in _BUILTIN_TEMPLATES:
                path = self._dir / f"{tpl_dict['id']}.json"
                if not path.exists():
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(tpl_dict, f, indent=2, ensure_ascii=False)

    # ── internal helpers ──────────────────────────────────────────────────

    def _path(self, template_id: str) -> Path:
        return self._dir / f"{template_id}.json"

    def _read(self, path: Path) -> WorkflowTemplate | None:
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return WorkflowTemplate(**json.load(f))

    def _write(self, template: WorkflowTemplate) -> None:
        path = self._path(template.id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(template.model_dump(), f, indent=2, ensure_ascii=False)

    # ── public API ────────────────────────────────────────────────────────

    def list_templates(
        self,
        category: str | None = None,
        search: str | None = None,
    ) -> list[WorkflowTemplate]:
        """Return templates, optionally filtered by *category* and/or *search*.

        When *search* is provided the filter matches against template name,
        description, and tags (case-insensitive).  Results are sorted by
        creation date (newest first).
        """
        if not self._dir.exists():
            return []

        paths = sorted(self._dir.glob("*.json"), reverse=True)
        result: list[WorkflowTemplate] = []
        for p in paths:
            tpl = self._read(p)
            if tpl is None:
                continue

            # Category filter
            if category and tpl.category != category:
                continue

            # Search filter (name, description, tags)
            if search:
                q = search.lower()
                if (
                    q not in tpl.name.lower()
                    and q not in tpl.description.lower()
                    and not any(q in tag.lower() for tag in tpl.tags)
                ):
                    continue

            result.append(tpl)
        return result

    def list_categories(self) -> list[dict]:
        """Return a list of distinct categories with template counts.

        Each entry: ``{"category": str, "count": int}``
        """
        counts: dict[str, int] = {}
        for p in self._dir.glob("*.json"):
            tpl = self._read(p)
            if tpl:
                cat = tpl.category or "general"
                counts[cat] = counts.get(cat, 0) + 1
        return [
            {"category": cat, "count": cnt}
            for cat, cnt in sorted(counts.items(), key=lambda x: -x[1])
        ]

    def get_template(self, template_id: str) -> WorkflowTemplate | None:
        """Retrieve a single template by its id, or *None*."""
        return self._read(self._path(template_id))

    def save_template(self, template: WorkflowTemplate) -> WorkflowTemplate:
        """Persist a template (create or update)."""
        template.updated_at = datetime.now().isoformat()
        self._write(template)
        return template

    def delete_template(self, template_id: str) -> bool:
        """Remove a template file.  Returns *True* on success."""
        path = self._path(template_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def increment_usage(self, template_id: str) -> WorkflowTemplate | None:
        """Increment the usage counter for a template and persist.

        Returns the updated template, or *None* if not found.
        """
        tpl = self.get_template(template_id)
        if tpl is None:
            return None
        tpl.usage_count += 1
        tpl.updated_at = datetime.now().isoformat()
        self._write(tpl)
        return tpl

    def instantiate(self, template_id: str) -> Workflow | None:
        """Create a new Workflow from a template.

        Every node and edge receives fresh random IDs so that instantiated
        workflows are fully independent of the template definition.
        """
        template = self.get_template(template_id)
        if template is None:
            return None

        # Build ID map: original -> fresh
        id_map: dict[str, str] = {}
        new_nodes: list[Node] = []
        for node in template.nodes:
            new_id = f"node_{uuid.uuid4().hex[:8]}"
            id_map[node.id] = new_id
            new_node = node.model_copy(update={
                "id": new_id,
                "status": NodeStatus.PENDING,
                "result": None,
                "error": None,
                "started_at": None,
                "completed_at": None,
            })
            new_nodes.append(new_node)

        new_edges: list[Edge] = []
        for edge in template.edges:
            new_edges.append(edge.model_copy(update={
                "id": f"edge_{uuid.uuid4().hex[:8]}",
                "source_id": id_map.get(edge.source_id, edge.source_id),
                "target_id": id_map.get(edge.target_id, edge.target_id),
            }))

        workflow = Workflow(
            id=f"wf_{uuid.uuid4().hex[:8]}",
            name=f"{template.name}",
            description=template.description,
            nodes=new_nodes,
            edges=new_edges,
            global_context=template.config.copy(),
            tags=template.tags.copy(),
        )

        # Bump usage counter
        template.usage_count += 1
        self.save_template(template)

        return workflow
