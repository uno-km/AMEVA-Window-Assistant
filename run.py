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


def _try_start_docker(logger):
    try:
        docker_dir = _PROJECT_ROOT / "docker"
        if (docker_dir / "docker-compose.yml").exists():
            logger.info("Starting Docker Compose...")
            subprocess.run(
                ["docker", "compose", "up", "-d"],
                cwd=str(docker_dir)
            )
            return True
    except Exception as e:
        logger.error(f"Failed to start Docker Compose: {e}")
    return False


def _stop_docker(logger):
    try:
        docker_dir = _PROJECT_ROOT / "docker"
        if (docker_dir / "docker-compose.yml").exists():
            logger.info("Stopping Docker Compose and cleaning up resources...")
            subprocess.run(
                ["docker", "compose", "down"],
                cwd=str(docker_dir)
            )
    except Exception as e:
        logger.error(f"Failed to stop Docker Compose: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    _bootstrap_dirs()

    logger = _setup_logging()
    logger.info("=== AMEVA Voice Screen Assistant starting ===")

    # Config singleton (already loaded on import)
    from src.config import CFG

    # Database setup early for logging errors
    from src.storage.db import DatabaseManager
    db_path = CFG.resolve_path(CFG.get("db", "path", default="db/ameva_assistant.db"))
    db = DatabaseManager(db_path)
    logger.info(f"Database ready: {db_path}")

    # Auto-start LLM and VLM servers if not alive
    llm_url = CFG.get("llm", "base_url", default="http://127.0.0.1:8080/v1")
    vlm_url = "http://127.0.0.1:8081/v1"
    
    max_retries = 5
    max_wait = 60
    
    servers_alive = False
    
    for attempt in range(1, max_retries + 1):
        llm_alive = _is_server_alive(llm_url)
        vlm_alive = _is_server_alive(vlm_url)
        
        if llm_alive and vlm_alive:
            servers_alive = True
            break
            
        logger.warning(f"LLM or VLM Server is unreachable. (Attempt {attempt}/{max_retries})")
        logger.info("Attempting to start servers via Docker Compose...")
        _try_start_docker(logger)
        
        logger.info(f"Waiting up to {max_wait}s for models to load into memory...")
        for _ in range(max_wait):
            time.sleep(1.0)
            if _is_server_alive(llm_url) and _is_server_alive(vlm_url):
                logger.info("LLM & VLM Servers successfully started via Docker!")
                servers_alive = True
                break
                
        if servers_alive:
            break
            
    if not servers_alive:
        err_msg = "Docker Compose failed to start the models after 5 attempts. Shutting down system."
        logger.error(err_msg)
        db.insert_log(level="ERROR", message=err_msg)
        _stop_docker(logger)
        sys.exit(1)

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
