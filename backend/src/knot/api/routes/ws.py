"""WebSocket endpoint for real-time execution status push."""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── WebSocket Connection Manager ────────────────────────────────────────


class WebSocketManager:
    """Manages WebSocket connections grouped by execution_id.

    Uses a dict[execution_id, set[WebSocket]] to track connected clients.
    Provides connect/disconnect/broadcast operations. Designed as a
    singleton so both the WS route and the workflow engine can reference
    the same instance.
    """

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, execution_id: str, ws: WebSocket) -> None:
        """Accept a new WebSocket connection and register it."""
        await ws.accept()
        self._connections.setdefault(execution_id, set()).add(ws)
        logger.debug(
            "WS client connected for execution %s (total: %d)",
            execution_id,
            len(self._connections[execution_id]),
        )

    async def disconnect(self, execution_id: str, ws: WebSocket) -> None:
        """Unregister a WebSocket connection."""
        clients = self._connections.get(execution_id)
        if clients:
            clients.discard(ws)
            if not clients:
                del self._connections[execution_id]
        logger.debug(
            "WS client disconnected for execution %s",
            execution_id,
        )

    async def broadcast(self, execution_id: str, data: dict[str, Any]) -> None:
        """Send a JSON message to every connected client for an execution.

        Silently removes stale connections (client already disconnected).
        """
        clients = list(self._connections.get(execution_id, set()))
        stale: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_json(data)
            except WebSocketDisconnect:
                stale.append(ws)
            except Exception:
                stale.append(ws)
        for ws in stale:
            await self.disconnect(execution_id, ws)

    @property
    def active_executions(self) -> list[str]:
        """Return list of execution_ids that have active subscribers."""
        return list(self._connections.keys())


# Singleton — shared between ws route handlers and WorkflowEngine.
ws_manager = WebSocketManager()


# ─── WebSocket Route ─────────────────────────────────────────────────────


@router.websocket("/api/v1/ws/executions/{execution_id}")
async def execution_ws(websocket: WebSocket, execution_id: str) -> None:
    """WebSocket endpoint for real-time execution status.

    Protocol:
      1. Client connects to ``ws://host/api/v1/ws/executions/{execution_id}``.
      2. Server immediately starts pushing ``execution_update`` messages.
      3. (Optional) Client may send ``{"type": "subscribe", "execution_id": "..."}``
         as a confirmation — the server ignores the message body and keeps
         the connection registered.

    Server-pushed message format::

        {
            "type": "execution_update",
            "data": { ... Execution model_dump() ... }
        }
    """
    await ws_manager.connect(execution_id, websocket)
    try:
        # Keep the connection alive and handle inbound messages.
        # Currently the only recognized message is an optional subscribe
        # confirmation; everything else is logged at debug level.
        while True:
            try:
                message = await websocket.receive_json()
                msg_type = message.get("type", "")
                if msg_type == "subscribe":
                    logger.debug(
                        "Subscription confirmed for execution %s", execution_id
                    )
                else:
                    logger.debug("Unknown WS message type: %s", msg_type)
            except json.JSONDecodeError:
                # Ignore malformed messages — they may be keep-alive pings.
                pass
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for execution %s", execution_id)
    except Exception as exc:
        logger.warning(
            "WebSocket error for execution %s: %s", execution_id, exc
        )
    finally:
        await ws_manager.disconnect(execution_id, websocket)
