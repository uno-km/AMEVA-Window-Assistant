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
# Server Health Check, GPU Auto-Detection & Native Fallback
# ---------------------------------------------------------------------------
import socket
import urllib.parse
import urllib.request
import subprocess
import time
import os

local_processes = []

def _is_server_alive(base_url):
    try:
        url = f"{base_url}/models"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _is_docker_available():
    try:
        res = subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0
    except Exception:
        return False


def detect_hardware_and_get_config(logger):
    # Try nvidia-smi first
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        if res.returncode == 0:
            lines = [line.strip() for line in res.stdout.strip().split("\n") if line.strip()]
            if lines:
                parts = lines[0].split(",")
                gpu_name = parts[0].strip()
                gpu_memory = int(parts[1].strip())
                logger.info(f"[GPU DETECTION] Detected GPU: {gpu_name} (VRAM: {gpu_memory}MB)")
                return "gpu", 99
    except Exception:
        pass

    # Try GPUtil
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        if len(gpus) > 0:
            logger.info(f"[GPU DETECTION] Detected GPU via GPUtil: {gpus[0].name} (VRAM: {gpus[0].memoryTotal}MB)")
            return "gpu", 99
    except Exception:
        pass

    logger.info("[GPU DETECTION] No GPU detected or failed to check. Using CPU mode.")
    return "cpu", 0


def _prepare_docker_override(logger, has_gpu):
    docker_dir = _PROJECT_ROOT / "docker"
    override_path = docker_dir / "docker-compose.override.yml"
    if has_gpu:
        logger.info("[GPU SETUP] Writing docker-compose.override.yml with CUDA acceleration...")
        override_content = """version: '3.8'

services:
  llm-server:
    image: ghcr.io/ggml-org/llama.cpp:server-cuda
    command: --model /models/qwen2.5-3b-instruct-q4_k_m.gguf --host 0.0.0.0 --port 8080 --ctx-size 8192 --n-gpu-layers 99
    environment:
      - NVIDIA_DISABLE_REQUIRE=1
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

  qwen-router-server:
    image: ghcr.io/ggml-org/llama.cpp:server-cuda
    command: --model /models/qwen2.5-0.5b-q4_k_m.gguf --host 0.0.0.0 --port 8082 --ctx-size 2048 --n-gpu-layers 99
    environment:
      - NVIDIA_DISABLE_REQUIRE=1
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

  qwen-vlm-server:
    image: ghcr.io/ggml-org/llama.cpp:server-cuda
    command: --model /models/Qwen2-VL-2B-Instruct-Q4_K_M.gguf --mmproj /models/mmproj-Qwen2-VL-2B-Instruct-f16.gguf --host 0.0.0.0 --port 8083 --ctx-size 4096 --n-gpu-layers 99
    environment:
      - NVIDIA_DISABLE_REQUIRE=1
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
"""
        try:
            with open(override_path, "w", encoding="utf-8") as f:
                f.write(override_content)
        except Exception as e:
            logger.error(f"Failed to write docker-compose.override.yml: {e}")
    else:
        if override_path.exists():
            logger.info("[GPU SETUP] Removing docker-compose.override.yml (using CPU mode)...")
            try:
                override_path.unlink()
            except Exception:
                pass


def _try_start_docker(logger):
    try:
        docker_dir = _PROJECT_ROOT / "docker"
        if (docker_dir / "docker-compose.yml").exists():
            logger.info("Starting Docker Compose...")
            subprocess.run(
                ["docker", "compose", "up", "-d", "--remove-orphans"],
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


def _try_start_local_servers(logger):
    global local_processes
    from src.config import CFG

    logger.info("Starting local native llama_cpp servers...")
    hw_mode, gpu_layers = detect_hardware_and_get_config(logger)

    llama_server_exe = CFG.get("llm", "llama_server_executable", default="C:/ameva/AI_Models/llama.cpp/llama-server.exe")
    if not os.path.exists(llama_server_exe):
        logger.error(f"[LOCAL SERVER ERROR] Native llama-server executable not found at: {llama_server_exe}")
        return False

    llm_model = "C:/ameva/models/llm/qwen2.5-3b-instruct-q4_k_m.gguf" if hw_mode == "gpu" else "C:/ameva/models/llm/Llama-3.2-1B-Instruct-Q4_K_M.gguf"

    configs = [
        ("llm-server", 8780, llm_model, ["--ctx-size", "8192"]),
        ("router-server", 8782, "C:/ameva/models/llm/qwen2.5-0.5b-q4_k_m.gguf", ["--ctx-size", "2048"]),
        ("vlm-server", 8783, "C:/ameva/models/vlm/Qwen2-VL-2B-Instruct-Q4_K_M.gguf", ["--ctx-size", "4096", "--mmproj", "C:/ameva/models/vlm/mmproj-Qwen2-VL-2B-Instruct-f16.gguf"])
    ]

    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    started = 0
    for name, port, model_path, extra in configs:
        if not os.path.exists(model_path):
            logger.error(f"[LOCAL SERVER ERROR] Model file not found: {model_path}")
            continue

        cmd = [
            llama_server_exe,
            "--model", model_path,
            "--host", "0.0.0.0",
            "--port", str(port),
            "--n-gpu-layers", str(gpu_layers)
        ] + extra

        logger.info(f"Spawning local native server '{name}' on port {port}: {' '.join(cmd)}")
        try:
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            proc = subprocess.Popen(
                cmd,
                startupinfo=startupinfo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env
            )
            local_processes.append(proc)
            started += 1
        except Exception as e:
            logger.error(f"Failed to start local server '{name}': {e}")

    return started > 0


def _stop_local_servers(logger):
    global local_processes
    if local_processes:
        logger.info("Stopping local llama_cpp servers...")
        for proc in local_processes:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        local_processes = []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    _bootstrap_dirs()

    logger = _setup_logging()
    logger.info("=== AMEVA Voice Screen Assistant starting ===")

    # Config singleton
    from src.config import CFG

    # Database setup early for logging errors
    from src.storage.db import DatabaseManager
    db_path = CFG.resolve_path(CFG.get("db", "path", default="db/ameva_assistant.db"))
    db = DatabaseManager(db_path)
    logger.info(f"Database ready: {db_path}")

    # Determine GPU settings
    hw_mode, gpu_layers = detect_hardware_and_get_config(logger)
    has_gpu = (hw_mode == "gpu")

    # Auto-start LLM and VLM servers if not alive
    llm_url = CFG.get("llm", "base_url", default="http://127.0.0.1:8780/v1")
    vlm_endpoint = CFG.get("vlm", "endpoint", default="http://127.0.0.1:8783/v1/chat/completions")
    router_endpoint = CFG.get("router", "endpoint", default="http://127.0.0.1:8782/v1/chat/completions")

    def _get_base_v1(url_str):
        if "/chat/completions" in url_str:
            return url_str.split("/chat/completions")[0]
        return url_str

    vlm_url = _get_base_v1(vlm_endpoint)
    router_url = _get_base_v1(router_endpoint)

    max_retries = 3
    max_wait = 45
    servers_alive = False

    use_docker = CFG.get("llm", "use_docker", default=True)
    docker_running = _is_docker_available() and use_docker

    for attempt in range(1, max_retries + 1):
        llm_alive = _is_server_alive(llm_url)
        vlm_alive = _is_server_alive(vlm_url)
        router_alive = _is_server_alive(router_url)

        if llm_alive and vlm_alive and router_alive:
            servers_alive = True
            break

        logger.warning(f"LLM, VLM or Router Server is unreachable. (Attempt {attempt}/{max_retries})")

        if docker_running:
            logger.info("Attempting to start servers via Docker Compose...")
            _prepare_docker_override(logger, has_gpu)
            _try_start_docker(logger)
        else:
            logger.info("Docker is not running/available or disabled. Attempting local native startup...")
            _try_start_local_servers(logger)

        logger.info(f"Waiting up to {max_wait}s for models to load into memory...")
        for _ in range(max_wait):
            time.sleep(1.0)
            if _is_server_alive(llm_url) and _is_server_alive(vlm_url) and _is_server_alive(router_url):
                logger.info("LLM, VLM & Router Servers successfully started!")
                servers_alive = True
                break

        if servers_alive:
            break

    if not servers_alive:
        err_msg = "Failed to start the model servers. Shutting down system."
        logger.error(err_msg)
        db.insert_log(level="ERROR", message=err_msg)
        if docker_running:
            _stop_docker(logger)
        else:
            _stop_local_servers(logger)
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

    try:
        app = MainWindow(db=db, cfg=CFG)
        logger.info("UI launched — entering main loop")
        app.mainloop()
    finally:
        logger.info("=== AMEVA Voice Screen Assistant stopping ===")
        if docker_running:
            _stop_docker(logger)
        else:
            _stop_local_servers(logger)
        logger.info("=== AMEVA Voice Screen Assistant stopped ===")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Application gracefully stopped by user (Ctrl+C).")
        sys.exit(0)




