"""
VARUNA Backend — WebSocket real-time alert system.

Clients connect to ``/ws/alerts`` and receive push notifications
whenever new divergence alerts are detected. This replaces the
frontend's 30-second polling with true real-time updates.

Architecture (Day 3 finalized):
─────────────────────────────────────────────────────────────────────
  AlertManager  (singleton)
      │
      ├── _connections : set[WebSocket]          — live frontend clients
      ├── _poll_task   : asyncio.Task             — background poller
      └── _previous_alert_ids : set[str]          — diff tracking

  Polling loop (every VARUNA_WS_ALERT_POLL_INTERVAL_S seconds, default 5s):
      1. Call upstream.get_alerts()  →  graph_fusion or mock fallback
      2. Diff against _previous_alert_ids  →  extract NEW alerts only
      3. If new alerts → broadcast as {"type":"alert", "payload":[...]}
      4. Every VARUNA_WS_HEARTBEAT_INTERVAL_S (default 30s) → heartbeat

  Client connection lifecycle:
      connect  → send connection_ack  → flush current alerts immediately
      receive  → handle client filter commands (region/severity)
      error    → clean disconnect, no cascading failures

Message envelope (all messages):
    {
        "type":      "connection_ack" | "alert" | "heartbeat" | "error",
        "payload":   <list[Alert]> | <dict> | null,
        "timestamp": "<ISO-8601 UTC>"
    }
─────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..config import get_settings

logger = logging.getLogger("varuna.websocket")

router = APIRouter(tags=["WebSocket"])


# ── internal client state ─────────────────────────────────────────────

class _ClientState:
    """
    Per-connection state for filter preferences.

    Clients may send a JSON command to filter which alerts they receive:
        {"action": "filter", "region": "bay_of_bengal", "min_severity": "warning"}

    Unrecognised commands are silently ignored.
    """

    def __init__(self) -> None:
        self.region_filter: str | None = None      # None = all regions
        self.min_severity: str | None = None       # None = all severities

    _SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}

    def matches(self, alert: dict) -> bool:
        """Return True if this alert should be forwarded to this client."""
        if self.region_filter and alert.get("region") != self.region_filter:
            return False
        if self.min_severity:
            alert_sev = self._SEVERITY_ORDER.get(alert.get("severity", "info"), 0)
            min_sev = self._SEVERITY_ORDER.get(self.min_severity, 0)
            if alert_sev < min_sev:
                return False
        return True

    def apply_command(self, raw: str) -> None:
        """Parse and apply a client filter command (JSON). Silently ignores invalid input."""
        try:
            cmd = json.loads(raw)
            if not isinstance(cmd, dict) or cmd.get("action") != "filter":
                return
            self.region_filter = cmd.get("region") or None
            self.min_severity = cmd.get("min_severity") or None
            logger.debug(
                "Client filter updated: region=%r, min_severity=%r",
                self.region_filter, self.min_severity,
            )
        except (json.JSONDecodeError, TypeError):
            pass  # malformed input — ignore silently


# ── AlertManager ──────────────────────────────────────────────────────

class AlertManager:
    """
    Manages WebSocket connections and broadcasts alert events.

    Day 3 additions vs Day 1 scaffold:
    ─────────────────────────────────────────────────────────────────
    • Per-client _ClientState for region / severity filtering
    • Immediate alert flush on new connection (no wait for first poll)
    • Structured error broadcast (type="error") on poll failure
    • Connection health counter on broadcast (dead socket removal)
    • Client command parsing: {"action":"filter","region":"...","min_severity":"..."}
    ─────────────────────────────────────────────────────────────────
    """

    def __init__(self) -> None:
        # ws → per-client filter state
        self._connections: dict[WebSocket, _ClientState] = {}
        self._previous_alert_ids: set[str] = set()
        self._latest_alerts: list[dict] = []        # cache for immediate flush
        self._poll_task: asyncio.Task | None = None
        self._consecutive_failures: int = 0

    # ── connection lifecycle ──────────────────────────────────────────

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def connect(self, ws: WebSocket) -> None:
        """
        Accept, register and immediately flush current alerts to the new client.

        Steps:
          1. Enforce max connection cap (reject with 1013 if at limit)
          2. Accept the WebSocket upgrade
          3. Send connection_ack with current server stats
          4. Flush any cached alerts so the client has data right away
        """
        settings = get_settings()
        if len(self._connections) >= settings.ws_max_connections:
            await ws.close(code=1013, reason="Max connections reached")
            return

        await ws.accept()
        self._connections[ws] = _ClientState()
        logger.info("WebSocket connected (%d total)", len(self._connections))

        # 1. Acknowledge connection with current stats
        await self._send(ws, {
            "type": "connection_ack",
            "payload": {
                "message": "Connected to VARUNA live alert stream",
                "active_connections": len(self._connections),
                "poll_interval_s": settings.ws_alert_poll_interval_s,
                "tip": (
                    'Send {"action":"filter","region":"bay_of_bengal",'
                    '"min_severity":"warning"} to filter alerts'
                ),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # 2. Immediately flush cached alerts so the client isn't blank
        if self._latest_alerts:
            client_state = self._connections[ws]
            visible = [a for a in self._latest_alerts if client_state.matches(a)]
            if visible:
                await self._send(ws, {
                    "type": "alert",
                    "payload": visible,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                logger.debug(
                    "Flushed %d alert(s) to newly connected client", len(visible)
                )

    def disconnect(self, ws: WebSocket) -> None:
        """Remove a WebSocket connection from the registry."""
        self._connections.pop(ws, None)
        logger.info("WebSocket disconnected (%d remaining)", len(self._connections))

    # ── broadcast helpers ─────────────────────────────────────────────

    async def broadcast(self, message: dict) -> None:
        """
        Send a message to ALL connected clients.

        Dead connections (send raises) are collected and pruned
        after the send loop to avoid mutating the dict during iteration.
        """
        if not self._connections:
            return

        dead: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await self._send(ws, message)
            except Exception as exc:
                logger.debug("Dead WebSocket detected during broadcast: %s", exc)
                dead.append(ws)

        for ws in dead:
            self._connections.pop(ws, None)

        if dead:
            logger.info(
                "Pruned %d dead connection(s); %d remaining",
                len(dead), len(self._connections),
            )

    async def broadcast_alerts(self, alerts: list[dict]) -> None:
        """
        Broadcast a list of new alerts, respecting each client's filter state.

        Unlike ``broadcast()``, this sends per-client filtered payloads so
        a client subscribed to only "critical" events doesn't receive "info".
        """
        if not alerts or not self._connections:
            return

        now_ts = datetime.now(timezone.utc).isoformat()
        dead: list[WebSocket] = []

        for ws, client_state in list(self._connections.items()):
            visible = [a for a in alerts if client_state.matches(a)]
            if not visible:
                continue
            try:
                await self._send(ws, {
                    "type": "alert",
                    "payload": visible,
                    "timestamp": now_ts,
                })
            except Exception as exc:
                logger.debug("Dead WebSocket on alert broadcast: %s", exc)
                dead.append(ws)

        for ws in dead:
            self._connections.pop(ws, None)

        logger.info(
            "Broadcast %d alert(s) to %d client(s) (%d pruned)",
            len(alerts), len(self._connections), len(dead),
        )

    async def _send(self, ws: WebSocket, data: dict) -> None:
        """Serialize and send JSON to a single WebSocket. Raises on failure."""
        await ws.send_text(json.dumps(data, default=str))

    async def _send_heartbeat(self) -> None:
        """Send a heartbeat ping carrying live connection count."""
        if not self._connections:
            return
        await self.broadcast({
            "type": "heartbeat",
            "payload": {
                "active_connections": len(self._connections),
                "consecutive_poll_failures": self._consecutive_failures,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # ── polling loop ──────────────────────────────────────────────────

    async def start_polling(self, app: Any) -> None:
        """
        Background alert polling loop (Day 3 finalized).

        Every ``poll_interval`` seconds:
          1. Fetch alerts from upstream.get_alerts()
             (= graph_fusion URL if reachable, else mock_data fallback)
          2. Cache in self._latest_alerts for immediate-flush to new clients
          3. Diff against _previous_alert_ids → only NEW alerts are broadcast
          4. Update _consecutive_failures counter for heartbeat diagnostics
          5. Periodically send a heartbeat

        The loop is designed never to crash:
          - CancelledError  → clean exit
          - Any other error → log + sleep + retry
        """
        settings = get_settings()
        poll_interval   = settings.ws_alert_poll_interval_s
        heartbeat_every = settings.ws_heartbeat_interval_s

        logger.info(
            "Alert polling started  poll=%.1fs  heartbeat=%.1fs",
            poll_interval, heartbeat_every,
        )

        heartbeat_counter = 0.0

        while True:
            try:
                await asyncio.sleep(poll_interval)
                heartbeat_counter += poll_interval

                # ── 1. Fetch alerts ───────────────────────────────────
                try:
                    upstream = app.state.upstream
                    raw_alerts: list[dict] = await upstream.get_alerts()
                    self._consecutive_failures = 0

                    # ── 2. Cache for new-client flush ─────────────────
                    self._latest_alerts = raw_alerts

                    # ── 3. Diff: only broadcast alerts we haven't seen ─
                    current_ids: set[str] = set()
                    new_alerts: list[dict] = []

                    for alert in raw_alerts:
                        alert_id = alert.get("id", "")
                        current_ids.add(alert_id)
                        if alert_id not in self._previous_alert_ids:
                            new_alerts.append(alert)

                    self._previous_alert_ids = current_ids

                    if new_alerts:
                        await self.broadcast_alerts(new_alerts)
                    else:
                        logger.debug("Poll: no new alerts (total=%d)", len(raw_alerts))

                except asyncio.CancelledError:
                    raise  # propagate to outer handler
                except Exception as exc:
                    self._consecutive_failures += 1
                    logger.warning(
                        "Alert poll failed (failure #%d): %s",
                        self._consecutive_failures, exc,
                    )
                    # After 3 consecutive failures, tell clients the source is degraded
                    if self._consecutive_failures == 3 and self._connections:
                        await self.broadcast({
                            "type": "error",
                            "payload": {
                                "message": "Alert source temporarily unavailable — retrying",
                                "consecutive_failures": self._consecutive_failures,
                            },
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })

                # ── 4. Periodic heartbeat ─────────────────────────────
                if heartbeat_counter >= heartbeat_every:
                    await self._send_heartbeat()
                    heartbeat_counter = 0.0

            except asyncio.CancelledError:
                logger.info("Alert polling stopped (CancelledError)")
                break
            except Exception:
                logger.exception("Unexpected error in alert polling loop — will retry")
                await asyncio.sleep(poll_interval)

    # ── task lifecycle ─────────────────────────────────────────────────

    def start(self, app: Any) -> None:
        """Launch the background polling task (idempotent)."""
        if self._poll_task is None or self._poll_task.done():
            self._poll_task = asyncio.create_task(
                self.start_polling(app),
                name="varuna-alert-poller",
            )
            logger.info("Alert polling task created")

    async def stop(self) -> None:
        """Cancel polling task, then gracefully close all WebSocket connections."""
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            logger.info("Alert polling task stopped")

        # Notify all clients before closing
        if self._connections:
            try:
                await self.broadcast({
                    "type": "error",
                    "payload": {"message": "Server shutting down"},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception:
                pass

        for ws in list(self._connections):
            try:
                await ws.close(code=1001, reason="Server shutting down")
            except Exception:
                pass
        self._connections.clear()
        logger.info("All WebSocket connections closed")


# ── module-level singleton ────────────────────────────────────────────

alert_manager = AlertManager()


# ── WebSocket endpoint ────────────────────────────────────────────────

@router.websocket("/ws/alerts")
async def websocket_alerts(ws: WebSocket) -> None:
    """
    WebSocket endpoint for real-time VARUNA alert streaming.

    Protocol:
    ─────────────────────────────────────────────────────────────────
    Server → Client messages (all JSON):
        {"type":"connection_ack", "payload":{...stats...}, "timestamp":"..."}
        {"type":"alert",          "payload":[{...alert...}, ...],  "timestamp":"..."}
        {"type":"heartbeat",      "payload":{...stats...}, "timestamp":"..."}
        {"type":"error",          "payload":{"message":"..."}, "timestamp":"..."}

    Client → Server messages (optional, JSON):
        {"action":"filter", "region":"bay_of_bengal", "min_severity":"warning"}
        — Sets a persistent per-connection filter. Omit fields to clear filter.
    ─────────────────────────────────────────────────────────────────
    Connect with:
        wscat -c ws://localhost:8000/ws/alerts
        # or in browser: new WebSocket('ws://localhost:8000/ws/alerts')
    """
    await alert_manager.connect(ws)
    if ws not in alert_manager._connections:
        # connect() rejected it (max connections) — nothing to do
        return

    try:
        while True:
            # Drive the connection alive; also handles incoming client commands
            raw = await ws.receive_text()
            client_state = alert_manager._connections.get(ws)
            if client_state:
                client_state.apply_command(raw)
    except WebSocketDisconnect:
        alert_manager.disconnect(ws)
    except Exception as exc:
        logger.debug("WebSocket error, disconnecting: %s", exc)
        alert_manager.disconnect(ws)
