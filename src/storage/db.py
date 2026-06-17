"""
AMEVA Voice Screen Assistant — Database Manager
================================================
SQLite3 facade handling schema creation and all CRUD operations.

Table naming follows the ``tb_`` prefix convention with abbreviated column
names (e.g. ``ttl`` for title, ``strt_dt`` for start datetime).

Thread safety: each public method opens and closes its own connection so
that the module can be called from any thread without external locking.
"""

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Timestamp helper
# ---------------------------------------------------------------------------
def _now() -> str:
    """Return current time as ISO-8601 string ``YYYY-MM-DD HH:MM:SS``."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Schema SQL
# ---------------------------------------------------------------------------
_SCHEMA_SQL = """
-- 1. Session table
CREATE TABLE IF NOT EXISTS tb_session (
    id          TEXT PRIMARY KEY,
    ttl         TEXT NOT NULL,
    strt_dt     TEXT NOT NULL,
    lst_actv_dt TEXT NOT NULL
);

-- 2. Message table
CREATE TABLE IF NOT EXISTS tb_message (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sess_id     TEXT    NOT NULL,
    role        TEXT    NOT NULL,
    content     TEXT    NOT NULL,
    create_dt   TEXT    NOT NULL,
    cap_path    TEXT,
    llm_prov    TEXT,
    llm_mdl     TEXT,
    vis_prov    TEXT,
    stt_prov    TEXT,
    tts_enbl    INTEGER DEFAULT 0,
    ltncy_ms    INTEGER,
    stts        TEXT    DEFAULT 'ok',
    FOREIGN KEY (sess_id) REFERENCES tb_session (id) ON DELETE CASCADE
);

-- 3. Job table
CREATE TABLE IF NOT EXISTS tb_job (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sess_id     TEXT    NOT NULL,
    stt_state   TEXT    DEFAULT 'queued',
    qd_dt       TEXT    NOT NULL,
    strt_dt     TEXT,
    fnsh_dt     TEXT,
    inp_txt     TEXT,
    cap_path    TEXT,
    llm_prov    TEXT,
    llm_mdl     TEXT,
    err_id      INTEGER,
    inp_mode    TEXT    DEFAULT 'text',
    route_decision TEXT,
    route_reason TEXT,
    FOREIGN KEY (sess_id) REFERENCES tb_session (id) ON DELETE CASCADE
);

-- 4. Log table
CREATE TABLE IF NOT EXISTS tb_log (
    log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     TEXT,
    level       TEXT    NOT NULL,
    message     TEXT    NOT NULL,
    traceback   TEXT,
    create_dt   TEXT    NOT NULL
);

-- 5. Secrets table (Vault)
CREATE TABLE IF NOT EXISTS tb_secrets (
    id              TEXT PRIMARY KEY,
    encrypted_value TEXT NOT NULL,
    description     TEXT,
    create_dt       TEXT NOT NULL
);
"""


# ---------------------------------------------------------------------------
# DatabaseManager
# ---------------------------------------------------------------------------
class DatabaseManager:
    """
    Facade over SQLite providing domain-specific CRUD helpers.

    Each method acquires its own ``sqlite3.Connection`` to avoid
    cross-thread issues.  Use ``WAL`` journal mode for better
    concurrency between the UI thread and the worker thread.
    """

    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # ------------------------------------------------------------------
    # Connection helper
    # ------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA_SQL)
            try:
                conn.execute("ALTER TABLE tb_job ADD COLUMN route_decision TEXT;")
                conn.execute("ALTER TABLE tb_job ADD COLUMN route_reason TEXT;")
            except sqlite3.OperationalError:
                pass
            conn.commit()
        finally:
            conn.close()

    # ==================================================================
    #  SESSION operations
    # ==================================================================
    def create_session(self, title: str = None) -> str:
        """Create a new session and return its UUID id."""
        sid = uuid.uuid4().hex[:12]
        now = _now()
        title = title or f"Session {now}"
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO tb_session (id, ttl, strt_dt, lst_actv_dt) "
                "VALUES (?, ?, ?, ?)",
                (sid, title, now, now),
            )
            conn.commit()
        finally:
            conn.close()
        return sid

    def list_sessions(self) -> list[dict]:
        """Return all sessions ordered by last activity (newest first)."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, ttl, strt_dt, lst_actv_dt "
                "FROM tb_session ORDER BY lst_actv_dt DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_session_active(self, session_id: str):
        """Touch the last-active timestamp."""
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE tb_session SET lst_actv_dt = ? WHERE id = ?",
                (_now(), session_id),
            )
            conn.commit()
        finally:
            conn.close()

    def update_session_title(self, session_id: str, title: str):
        """Rename a session."""
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE tb_session SET ttl = ? WHERE id = ?",
                (title, session_id),
            )
            conn.commit()
        finally:
            conn.close()

    # ==================================================================
    #  MESSAGE operations
    # ==================================================================
    def insert_message(
        self,
        sess_id: str,
        role: str,
        content: str,
        *,
        cap_path: str = None,
        llm_prov: str = None,
        llm_mdl: str = None,
        vis_prov: str = None,
        stt_prov: str = None,
        tts_enbl: bool = False,
        ltncy_ms: int = None,
        stts: str = "ok",
    ) -> int:
        """Insert a chat message and return its auto-incremented id."""
        conn = self._connect()
        try:
            cur = conn.execute(
                "INSERT INTO tb_message "
                "(sess_id, role, content, create_dt, cap_path, "
                " llm_prov, llm_mdl, vis_prov, stt_prov, tts_enbl, ltncy_ms, stts) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    sess_id,
                    role,
                    content,
                    _now(),
                    cap_path,
                    llm_prov,
                    llm_mdl,
                    vis_prov,
                    stt_prov,
                    1 if tts_enbl else 0,
                    ltncy_ms,
                    stts,
                ),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_messages(self, sess_id: str) -> list[dict]:
        """Fetch all messages for a session ordered by creation time."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM tb_message WHERE sess_id = ? ORDER BY create_dt ASC",
                (sess_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ==================================================================
    #  JOB operations
    # ==================================================================
    def insert_job(
        self,
        sess_id: str,
        inp_txt: str,
        *,
        cap_path: str = None,
        llm_prov: str = None,
        llm_mdl: str = None,
        inp_mode: str = "text",
    ) -> int:
        """Enqueue a new job and return its id."""
        conn = self._connect()
        try:
            cur = conn.execute(
                "INSERT INTO tb_job "
                "(sess_id, stt_state, qd_dt, inp_txt, cap_path, "
                " llm_prov, llm_mdl, inp_mode) "
                "VALUES (?, 'queued', ?, ?, ?, ?, ?, ?)",
                (sess_id, _now(), inp_txt, cap_path, llm_prov, llm_mdl, inp_mode),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def update_job_state(
        self,
        job_id: int,
        state: str,
        *,
        err_id: int = None,
    ):
        """
        Transition a job to a new state.

        Automatically sets ``strt_dt`` when entering ``running`` and
        ``fnsh_dt`` when entering ``done`` or ``error``.
        """
        now = _now()
        conn = self._connect()
        try:
            if state == "running":
                conn.execute(
                    "UPDATE tb_job SET stt_state = ?, strt_dt = ? WHERE id = ?",
                    (state, now, job_id),
                )
            elif state in ("done", "error"):
                conn.execute(
                    "UPDATE tb_job SET stt_state = ?, fnsh_dt = ?, err_id = ? "
                    "WHERE id = ?",
                    (state, now, err_id, job_id),
                )
            else:
                conn.execute(
                    "UPDATE tb_job SET stt_state = ? WHERE id = ?",
                    (state, job_id),
                )
            conn.commit()
        finally:
            conn.close()

    def get_queued_count(self) -> int:
        """Return the number of jobs still in ``queued`` state."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM tb_job WHERE stt_state = 'queued'"
            ).fetchone()
            return row["cnt"]
        finally:
            conn.close()

    def update_job_routing(self, job_id: int, decision: str, reason: str):
        """Update job with the intent router's decision and reasoning."""
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE tb_job SET route_decision = ?, route_reason = ? WHERE id = ?",
                (decision, reason, job_id),
            )
            conn.commit()
        finally:
            conn.close()

    # ==================================================================
    #  LOG operations
    # ==================================================================
    def insert_log(
        self,
        *,
        task_id: str = None,
        level: str = "INFO",
        message: str = "",
        tb: str = None,
    ) -> int:
        """Write a log entry and return its ``log_id``."""
        conn = self._connect()
        try:
            cur = conn.execute(
                "INSERT INTO tb_log (task_id, level, message, traceback, create_dt) "
                "VALUES (?, ?, ?, ?, ?)",
                (task_id, level, message, tb, _now()),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_recent_logs(self, limit: int = 50) -> list[dict]:
        """Return the most recent log entries."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM tb_log ORDER BY create_dt DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ==================================================================
    #  VAULT (Secrets) operations
    # ==================================================================
    def save_secret(self, secret_id: str, encrypted_value: str, description: str = ""):
        """Insert or update an encrypted secret in the Vault."""
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO tb_secrets (id, encrypted_value, description, create_dt) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET "
                "encrypted_value=excluded.encrypted_value, "
                "description=excluded.description, "
                "create_dt=excluded.create_dt",
                (secret_id, encrypted_value, description, _now())
            )
            conn.commit()
        finally:
            conn.close()

    def get_secret(self, secret_id: str) -> str:
        """Retrieve the encrypted value of a secret by its ID."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT encrypted_value FROM tb_secrets WHERE id = ?",
                (secret_id,)
            ).fetchone()
            return row["encrypted_value"] if row else ""
        finally:
            conn.close()

    def delete_secret(self, secret_id: str):
        """Delete a secret from the Vault."""
        conn = self._connect()
        try:
            conn.execute("DELETE FROM tb_secrets WHERE id = ?", (secret_id,))
            conn.commit()
        finally:
            conn.close()
