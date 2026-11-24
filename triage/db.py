"""SQLite persistence for ticket state and an audit trail of node transitions."""
import json
import sqlite3
from pathlib import Path


class TicketStore:
    def __init__(self, path: str | Path = "tickets.db"):
        self.path = str(path)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                status TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL,
                node TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

    def save_state(self, state: dict) -> None:
        ticket_id = state["ticket"]["ticket_id"]
        self._conn.execute(
            """INSERT INTO tickets (ticket_id, state_json, status) VALUES (?, ?, ?)
               ON CONFLICT(ticket_id) DO UPDATE SET
                 state_json=excluded.state_json, status=excluded.status,
                 updated_at=CURRENT_TIMESTAMP""",
            (ticket_id, json.dumps(state), state.get("status", "unknown")),
        )
        self._conn.commit()

    def log_event(self, ticket_id: str, node: str, payload: dict) -> None:
        self._conn.execute(
            "INSERT INTO events (ticket_id, node, payload_json) VALUES (?, ?, ?)",
            (ticket_id, node, json.dumps(payload)),
        )
        self._conn.commit()

    def get_state(self, ticket_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT state_json FROM tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        return json.loads(row["state_json"]) if row else None

    def get_events(self, ticket_id: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT node FROM events WHERE ticket_id = ? ORDER BY id", (ticket_id,)
        ).fetchall()
        return [r["node"] for r in rows]

    def list_by_status(self, status: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT ticket_id FROM tickets WHERE status = ? ORDER BY ticket_id", (status,)
        ).fetchall()
        return [r["ticket_id"] for r in rows]
