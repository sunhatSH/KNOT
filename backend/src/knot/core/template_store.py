"""File-based persistence for WorkflowTemplate objects.

Templates are stored as individual JSON files under ``backend/data/templates/``.
This avoids coupling the template system to the main database so that templates
can be pre-seeded and easily shared.
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


class TemplateStore:
    """File-based CRUD for workflow templates."""

    def __init__(self, templates_dir: str | Path | None = None) -> None:
        self._dir = Path(templates_dir) if templates_dir else TEMPLATES_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

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

    def list_templates(self) -> list[WorkflowTemplate]:
        """Return all templates sorted by creation date (newest first)."""
        if not self._dir.exists():
            return []
        paths = sorted(self._dir.glob("*.json"), reverse=True)
        result: list[WorkflowTemplate] = []
        for p in paths:
            tpl = self._read(p)
            if tpl:
                result.append(tpl)
        return result

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
