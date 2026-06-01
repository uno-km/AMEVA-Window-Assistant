"""
AMEVA Voice Screen Assistant — Application Entry Point
======================================================
Usage::

    python run.py

Bootstraps runtime directories, initialises the database, binds the
exception guard, and launches the Tkinter main loop.
"""

import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure src/ is importable
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Bootstrap runtime directories
# ---------------------------------------------------------------------------
def _bootstrap_dirs():
    """Create required runtime directories if they don't exist."""
    dirs = [
        _PROJECT_ROOT / "db",
        _PROJECT_ROOT / "logs",
        _PROJECT_ROOT / "data" / "captures",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Setup logging
# ---------------------------------------------------------------------------
def _setup_logging():
    """Configure rotating file + console logging."""
    from src.config import CFG
    from logging.handlers import RotatingFileHandler

    log_dir = CFG.resolve_path(CFG.get("logging", "log_dir", default="logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / CFG.get("logging", "log_file", default="app.log")

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-7s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler (rotating)
    fh = RotatingFileHandler(
        str(log_file),
        maxBytes=CFG.get("logging", "max_bytes", default=5_242_880),
        backupCount=CFG.get("logging", "backup_count", default=3),
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)

    root = logging.getLogger("ameva")
    root.setLevel(logging.DEBUG)
    root.addHandler(fh)
    root.addHandler(ch)

    return root


# ---------------------------------------------------------------------------
# Server Health Check and Launcher
# ---------------------------------------------------------------------------
import socket
import urllib.parse
import urllib.request
import subprocess
import time

def _is_server_alive(base_url):
    try:
        # Perform an actual HTTP GET to /models to verify it's a genuine LLM server
        url = f"{base_url}/models"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _try_start_docker():
    try:
        docker_dir = _PROJECT_ROOT / "docker"
        if (docker_dir / "docker-compose.yml").exists():
            subprocess.run(
                ["docker", "compose", "up", "-d"],
                cwd=str(docker_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5
            )
            return True
    except Exception:
        pass
    return False


def _start_mock_server(port):
    try:
        mock_script = _PROJECT_ROOT / "tests_harness" / "mock_llm_server.py"
        if mock_script.exists():
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = 0x00000010  # CREATE_NEW_CONSOLE
            
            subprocess.Popen(
                [sys.executable, str(mock_script), "--port", str(port)],
                creationflags=creation_flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    _bootstrap_dirs()

    logger = _setup_logging()
    logger.info("=== AMEVA Voice Screen Assistant starting ===")

    # Config singleton (already loaded on import)
    from src.config import CFG

    # Auto-start LLM and VLM servers if not alive
    llm_url = CFG.get("llm", "base_url", default="http://127.0.0.1:8080/v1")
    vlm_url = "http://127.0.0.1:8081/v1"
    
    llm_alive = _is_server_alive(llm_url)
    vlm_alive = _is_server_alive(vlm_url)

    if not llm_alive or not vlm_alive:
        logger.warning("LLM or VLM Server is unreachable.")
        logger.info("Attempting to start servers via Docker Compose...")
        _try_start_docker()
        
        # Wait up to 30 seconds for the heavy models to load into memory
        max_wait = 30
        logger.info(f"Waiting up to {max_wait}s for models to load into memory...")
        for _ in range(max_wait):
            time.sleep(1.0)
            if _is_server_alive(llm_url) and _is_server_alive(vlm_url):
                logger.info("LLM & VLM Servers successfully started via Docker!")
                break
        else:
            logger.warning("Docker Compose failed or models took too long to load.")
            if not _is_server_alive(llm_url):
                logger.info("Starting Mock LLM Server on port 8080...")
                _start_mock_server(8080)
            if not _is_server_alive(vlm_url):
                logger.info("Starting Mock VLM Server on port 8081...")
                _start_mock_server(8081)
            time.sleep(1.5)

    # Database
    from src.storage.db import DatabaseManager

    db_path = CFG.resolve_path(CFG.get("db", "path", default="db/ameva_assistant.db"))
    db = DatabaseManager(db_path)
    logger.info(f"Database ready: {db_path}")

    # Bind DB to exception guard
    from src.guard import set_db_ref

    set_db_ref(db)

    # Ensure at least one session exists
    sessions = db.list_sessions()
    if not sessions:
        sid = db.create_session("기본 세션")
        logger.info(f"Created default session: {sid}")

    # Launch UI
    from src.ui.ui_main import MainWindow

    app = MainWindow(db=db, cfg=CFG)
    logger.info("UI launched — entering main loop")
    app.mainloop()

    logger.info("=== AMEVA Voice Screen Assistant stopped ===")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Application gracefully stopped by user (Ctrl+C).")
        sys.exit(0)
