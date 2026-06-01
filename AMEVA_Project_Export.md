# AMEVA Voice Screen Assistant - Project Export

This document contains the complete architecture, implementation plans, tasks, and source code of the AMEVA project.

## 1. Architecture & Design Documents

### Document: implementation_plan.md

# Phase 3: Hybrid OCR + Multimodal Fallback Architecture & UI

사용자님의 엄격한 보안 요구사항(망분리 완전 로컬)과 아키텍처 규칙을 반영한 최종 설계도입니다.

## User Review Required

> [!IMPORTANT]
> **설계 확정 및 실행 승인 대기**
> 아래 설계가 사용자가 명시한 모든 제약 조건(오프라인 전용 VLM, 최대 3회 재시도, 5가지 Fallback 조건)을 완벽히 만족하는지 확인해 주십시오. 승인하시면 즉시 코딩(Execution)에 돌입합니다!

## Proposed Changes

---

### 1. Perception & UI Layer (Monitor Selection)

#### [MODIFY] src/ui/ui_main.py
- 드롭다운/라디오 버튼으로 캡처 대상을 선택할 수 있도록 UI 요소 추가 (`전체 화면`, `모니터 1`, `모니터 2` 등).
- `ScreenCapture.list_monitors()`를 활용하여 동적 바인딩.

#### [MODIFY] src/orchestration/worker.py
- UI에서 전달받은 `mode`와 `monitor_index`를 `capture()` 호출 시 인자로 전달.

---

### 2. Orchestration Layer (Router & Retry Logic)

#### [NEW] src/orchestration/router.py
- **Fallback Conditions (라우팅 규칙)**:
  1. OCR text block count < N
  2. Average OCR confidence < T
  3. 사용자 질문에 시각적/공간적 의도 포함 (`어디`, `버튼`, `아이콘`, `모양`, `색깔`, `그림`, `눌러`, `위치`)
  4. 1차 Text LLM 응답에 실패/애매함 키워드 포함 (`정확히 판단하기 어렵다`, `알 수 없다`, `OCR 결과가 불명확하다`)
  5. `scene_graph`의 `screen_type` 분류 실패 (unknown)
- 위 조건 중 하나라도 만족하면 VLM Fallback 경로로 작업(Job)을 라우팅.

#### [MODIFY] src/orchestration/worker.py
- **Auto-Retry & 무한루프 방지**: 라우터가 Fallback을 결정하면 VLM 워커로 작업을 넘김. 단, `job.retry_count`를 도입하여 최대 **3회**까지만 재시도하도록 제한.

---

### 3. Reasoning Layer (Strictly Local VLM Client)

#### [NEW] src/reasoning/vlm_client.py
- **Local-Only Provider Adapters**: 모든 VLM 백엔드는 로컬/오프라인 전용으로 설계. 클라우드, API(GPT-4o 등), 원격 URL 업로드는 **명시적으로 금지**.
- **Adapter Interface**:
  - `LocalLlamaCppMultimodalAdapter`: 로컬 llama.cpp (mmproj 포함) 전용 어댑터.
  - `LocalMockMultimodalAdapter`: 실제 로컬 VLM이 준비되지 않았을 때 파이프라인을 테스트하기 위한 Mock 어댑터.
- 하드코딩 모델명 배제, 설정값으로 모델 관리.

---

## Verification Plan

### Automated Tests
- `pytest tests_harness/test_router.py`:
  - 5가지 Fallback 조건(OCR 부족, 특정 단어 포함, LLM 실패 응답 등)이 각각 정확히 VLM 라우팅을 트리거하는지 검증.
  - 재시도 횟수가 3회를 초과할 경우 안전하게 Fallback을 포기하는지 검증.
- `pytest tests_harness/test_vlm_client.py`:
  - Mock 어댑터를 통해 로컬 멀티모달 포맷이 정상적으로 생성 및 반환되는지 검증.


---

### Document: task.md

# Phase 3: Hybrid OCR + Multimodal Fallback & UI

## 1. Perception & UI Layer
- [x] Add Monitor Selection dropdown in `src/ui/ui_main.py`
- [x] Bind `ScreenCapture.list_monitors()` to UI
- [x] Pass `mode` and `monitor_index` to `worker.py`

## 2. Reasoning Layer (Strictly Local VLM Client)
- [x] Create `src/reasoning/vlm_client.py`
- [x] Implement `LocalMockMultimodalAdapter`
- [x] Implement `LocalLlamaCppMultimodalAdapter`
- [x] Add Graceful Fallback (`local_vlm_unavailable`)

## 3. Orchestration Layer (Router)
- [x] Create `src/orchestration/router.py`
- [x] Implement `Fast-track multimodal routing` (Affordance keywords)
- [x] Implement `Retry-based multimodal fallback` (OCR block count < 5, confidence < 0.55, chars < 20, LLM failure phrases)

## 4. Orchestration Layer (Worker modifications)
- [x] Add `semantic_fallback_used` (max 1) and `backend_retry_count` (max 3)
- [x] Integrate `router.py` to decide VLM vs Text LLM
- [x] Refactor LLM call loop to support Fallback retry flow

## 5. Automated Tests
- [x] Create `tests_harness/test_router.py`
- [x] Create `tests_harness/test_vlm_client.py`


---

### Document: walkthrough.md

# Phase 3 완료: Hybrid Multimodal Fallback & Monitor Selection

승인해주신 아키텍처 설계를 기반으로, 완벽한 로컬 망분리 환경에서 동작하는 **하이브리드 VLM Fallback 시스템**과 **다중 모니터 선택 UI** 구현을 성공적으로 완료했습니다.

## 1. 캡처 대상 모니터 선택 UI 추가

[ui_main.py](file:///c:/ameva/AMEVA-Window-Assistant/src/ui/ui_main.py) 하단 `Send` 버튼 옆에 사용자의 디스플레이 환경을 동적으로 읽어오는 드롭다운을 추가했습니다.
이제 "전체 화면" 뿐만 아니라 "모니터 1", "모니터 2" 등 특정 화면만 골라서 캡처 후 분석할 수 있습니다. 수동 캡처(Capture 버튼)에도 동일하게 적용됩니다.

## 2. 깐깐한 조건부 라우팅 (Fallback Router)

[router.py](file:///c:/ameva/AMEVA-Window-Assistant/src/orchestration/router.py)에 명시해주신 5가지 조건을 완벽히 구현했습니다.
- **Fast-track**: `어디`, `버튼` 등 시각적 의도가 담긴 키워드 감지 시 OCR 단계를 건너뛰고 바로 VLM 호출
- **OCR 품질 검증**: Text block 5개 미만, 총 문자열 길이 20자 미만, 평균 Confidence 0.55 미만일 경우 Fallback
- **LLM 응답 실패 감지**: 1차 LLM이 `정확히 판단하기 어렵다`, `알 수 없다` 등의 문구를 반환하면 VLM 재시도
- **Scene Graph 실패 감지**: 화면 유형이 `unknown_application` 일 경우 Fallback

## 3. 철저한 망분리 VLM 클라이언트 (Local Only)

[vlm_client.py](file:///c:/ameva/AMEVA-Window-Assistant/src/reasoning/vlm_client.py)는 그 어떠한 외부 통신도 허용하지 않도록 엄격한 어댑터 패턴으로 구현되었습니다.
- **LocalLlamaCppMultimodalAdapter**: 로컬에 떠 있는 llama.cpp 서버로 로컬 이미지 바이트를 Base64 변환 후 전송합니다.
- **LocalMockMultimodalAdapter**: 로컬 VLM이 켜져있지 않거나 다운되었을 때 안전하게 우회하기 위해 `local_vlm_unavailable` 이라는 정형화된 JSON을 반환하며 장애 확산을 막습니다.

## 4. 백그라운드 재시도 정책 및 무한루프 차단

[worker.py](file:///c:/ameva/AMEVA-Window-Assistant/src/orchestration/worker.py)를 대대적으로 리팩토링했습니다.
- `semantic_fallback_used`: 한 개의 작업(Job) 당 VLM으로의 "의미적" 에스컬레이션은 **단 1회**만 발생하도록 막아 무한 핑퐁을 방지합니다.
- `backend_retry_count`: 로컬 VLM 서버 응답 지연 등 런타임 오류가 발생하면 최대 3번까지 재시도한 뒤 우아하게 포기합니다.

## 자동화 테스트 결과

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0
rootdir: C:\ameva\AMEVA-Window-Assistant
plugins: anyio-4.13.0
collected 5 items

tests_harness\test_router.py ...                                         [ 60%]
tests_harness\test_vlm_client.py ..                                      [100%]

============================== 5 passed in 4.14s ==============================
```

> [!TIP]
> 백그라운드에서는 4.58GB 짜리 Llama-3.1-8B 모델 다운로드(`Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf`)도 무사히 100% 완료되었습니다! 이제 이 시스템은 어떠한 외부 인터넷 연결도 필요 없는 강력하고 완전한 온프레미스 AI Assistant가 되었습니다.


---

## 2. Source Code

### File: .\run.py
`python
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

    # Auto-start LLM server if not alive
    base_url = CFG.get("llm", "base_url", default="http://127.0.0.1:8080/v1")
    p = urllib.parse.urlparse(base_url)
    host = p.hostname or '127.0.0.1'
    port = p.port or 8080

    if not _is_server_alive(base_url):
        logger.warning(f"LLM Server at {base_url} is unreachable.")
        logger.info("Attempting to start LLM server via Docker Compose...")
        _try_start_docker()
        
        # Wait a bit and recheck
        time.sleep(2.0)
        if _is_server_alive(base_url):
            logger.info("LLM Server successfully started via Docker!")
        else:
            logger.warning("Docker Compose failed or daemon is offline.")
            logger.info(f"Starting Mock LLM Server on port {port}...")
            _start_mock_server(port)
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
    main()

`

### File: .\run_app.bat
`bat
@echo off
title AMEVA Voice Screen Assistant
cd /d "%~dp0"

echo Starting AMEVA Voice Screen Assistant...
echo.

echo [INFO] Starting LLM server via Docker Compose (if not already running)...
cd docker
docker compose up -d
cd ..
echo.

if not exist venv\Scripts\activate.bat goto no_venv
echo [INFO] Activating virtual environment (venv)...
call venv\Scripts\activate.bat
goto run_app

:no_venv
echo [WARNING] virtual environment (venv) not found.
echo Running with system default python...

:run_app
echo.
python run.py
if errorlevel 1 goto error_exit
goto end

:error_exit
echo.
echo [ERROR] Application exited with error code %ERRORLEVEL%.
pause

:end

`

### File: .\.pytest_cache\README.md
`markdown
# pytest cache directory #

This directory contains data from the pytest's cache plugin,
which provides the `--lf` and `--ff` options, as well as the `cache` fixture.

**Do not** commit this to version control.

See [the docs](https://docs.pytest.org/en/stable/how-to/cache.html) for more information.

`

### File: .\docker\docker-compose.yml
`yaml
version: "3.8"

services:
  llama-server:
    image: ghcr.io/ggml-org/llama.cpp:server
    container_name: ameva-llm-server
    ports:
      - "8080:8080"
    volumes:
      # Mounted your actual model directory
      - C:/ameva/models:/models
    command: >
      --model /models/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf
      --host 0.0.0.0
      --port 8080
      --ctx-size 8192
      --n-gpu-layers 0
    restart: unless-stopped

  vlm-server:
    image: ghcr.io/ggml-org/llama.cpp:server
    container_name: ameva-vlm-server
    ports:
      - "8081:8081"
    volumes:
      - C:/ameva/models:/models
    command: >
      --model /models/moondream2-text-model-f16_ct-vicuna.gguf
      --mmproj /models/moondream2-mmproj-f16-20250414.gguf
      --host 0.0.0.0
      --port 8081
      --ctx-size 2048
      --n-gpu-layers 0
    restart: unless-stopped

`

### File: .\docker\README_docker.md
`markdown
# llama.cpp Docker 설정 가이드

## 사전 준비

1. Docker Desktop이 설치되어 있어야 합니다.
2. GGUF 모델 파일을 `docker/models/` 디렉토리에 배치합니다.

## 실행 방법

```powershell
cd docker

# docker-compose.yml에서 모델 파일명 수정 후 실행
docker compose up -d

# 상태 확인
docker compose ps

# 로그 보기
docker compose logs -f

# 중지
docker compose down
```

## Health Check

```powershell
# 서버 상태 확인
curl http://127.0.0.1:8080/v1/models

# 테스트 요청
curl -X POST http://127.0.0.1:8080/v1/chat/completions `
  -H "Content-Type: application/json" `
  -d '{"model":"local-gguf","messages":[{"role":"user","content":"Hello"}]}'
```

## 참고 자료

- [llama.cpp server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- [llama.cpp Docker 가이드](https://lindevs.com/install-llama-cpp-server-inside-docker-container-on-linux)

`

### File: .\src\config.py
`python
"""
AMEVA Voice Screen Assistant — Configuration Manager
=====================================================
Single-source configuration via config.json.
Exposes a global singleton `CFG` that all modules import.
"""

import json
import os
import threading
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config.json"

# ---------------------------------------------------------------------------
# Default configuration (used when config.json is missing or incomplete)
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "llm": {
        "base_url": "http://127.0.0.1:8080/v1",
        "model_alias": "local-gguf",
        "temperature": 0.2,
        "max_tokens": 512,
        "timeout_sec": 300,
        "system_prompt": (
            "You are a helpful desktop assistant. "
            "Analyze the user's screen context and answer their questions clearly."
        ),
    },
    "docker": {
        "image": "ghcr.io/ggml-org/llama.cpp:server",
        "container_name": "ameva-llm-server",
        "port": 8080,
        "model_dir": "",
        "model_file": "",
        "extra_args": "",
    },
    "capture": {
        "mode": "full",
        "monitor_index": 0,
        "root_dir": "data/captures",
        "auto_capture": True,
    },
    "stt": {
        "provider": "whisper_cpp",
        "whisper_executable": "",
        "whisper_model": "",
        "recording_max_sec": 30,
    },
    "tts": {
        "provider": "windows_sapi",
        "enabled": False,
    },
    "vision": {
        "provider": "none",
    },
    "db": {
        "path": "db/ameva_assistant.db",
    },
    "logging": {
        "log_dir": "logs",
        "log_file": "app.log",
        "max_bytes": 5_242_880,
        "backup_count": 3,
    },
}


# ---------------------------------------------------------------------------
# Deep merge utility
# ---------------------------------------------------------------------------
def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base*, returning a new dict."""
    merged = base.copy()
    for key, val in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
            merged[key] = _deep_merge(merged[key], val)
        else:
            merged[key] = val
    return merged


# ---------------------------------------------------------------------------
# AppConfig class
# ---------------------------------------------------------------------------
class AppConfig:
    """
    Thread-safe, singleton-ready configuration object.

    Usage::

        from src.config import CFG
        url = CFG.get("llm", "base_url")
        CFG.set("tts", "enabled", True)   # persists immediately
    """

    def __init__(self, config_path: Path | str = _CONFIG_PATH):
        self._path = Path(config_path)
        self._lock = threading.Lock()
        self._data: dict = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get(self, *keys: str, default=None):
        """
        Retrieve a nested value.

        ``CFG.get("llm", "base_url")``  →  ``"http://127.0.0.1:8080/v1"``
        """
        with self._lock:
            node = self._data
            for k in keys:
                if isinstance(node, dict) and k in node:
                    node = node[k]
                else:
                    return default
            return node

    def set(self, *keys_and_value):
        """
        Set a nested value and persist to disk.

        ``CFG.set("tts", "enabled", True)``
        """
        if len(keys_and_value) < 2:
            raise ValueError("Need at least one key and a value")
        keys = keys_and_value[:-1]
        value = keys_and_value[-1]
        with self._lock:
            node = self._data
            for k in keys[:-1]:
                node = node.setdefault(k, {})
            node[keys[-1]] = value
            self._save()

    def get_section(self, section: str) -> dict:
        """Return a full top-level section as a dict copy."""
        with self._lock:
            return dict(self._data.get(section, {}))

    def as_dict(self) -> dict:
        """Return the entire configuration as a deep copy."""
        import copy
        with self._lock:
            return copy.deepcopy(self._data)

    def reload(self):
        """Re-read config.json from disk."""
        self._load()

    @property
    def project_root(self) -> Path:
        return _PROJECT_ROOT

    def resolve_path(self, relative: str) -> Path:
        """Convert a project-relative path to an absolute path."""
        p = Path(relative)
        if p.is_absolute():
            return p
        return _PROJECT_ROOT / p

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _load(self):
        with self._lock:
            if self._path.exists():
                with open(self._path, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                self._data = _deep_merge(_DEFAULTS, user_data)
            else:
                self._data = _DEFAULTS.copy()
                self._save()

    def _save(self):
        """Persist current state to config.json (caller must hold _lock)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=4, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------
CFG = AppConfig()

`

### File: .\src\guard.py
`python
"""
AMEVA Voice Screen Assistant — Exception Guard
===============================================
Decorator that wraps critical functions to prevent uncaught crashes.
Errors are logged to both the Python logger and the SQLite ``tb_log`` table.
"""

import functools
import logging
import traceback

logger = logging.getLogger("ameva")

# ---------------------------------------------------------------------------
# Late-bound database reference
# ---------------------------------------------------------------------------
# We avoid a circular import by storing a reference that ``run.py`` sets
# after the database is initialized.
_db_ref = None


def set_db_ref(db):
    """Called once at startup to bind the database manager for error logging."""
    global _db_ref
    _db_ref = db


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------
def exception_guard(location: str = None, reraise: bool = False):
    """
    Wrap a function so that any unhandled exception is caught, logged, and
    optionally re-raised.

    Parameters
    ----------
    location : str, optional
        Human-readable label for the error origin (e.g. ``"worker.run"``).
        Defaults to the decorated function's qualified name.
    reraise : bool
        If ``True``, the exception is re-raised after logging.

    Example
    -------
    ::

        @exception_guard(location="capture.full_screen")
        def capture_full():
            ...
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            loc = location or f"{func.__qualname__}()"
            try:
                return func(*args, **kwargs)
            except Exception as e:
                tb_str = traceback.format_exc()
                msg = f"[{loc}] {type(e).__name__}: {e}"
                logger.error(msg, exc_info=True)

                # Attempt to persist to database
                if _db_ref is not None:
                    try:
                        _db_ref.insert_log(
                            task_id=None,
                            level="ERROR",
                            message=msg,
                            tb=tb_str,
                        )
                    except Exception:
                        logger.warning(
                            "Failed to write error to tb_log", exc_info=True
                        )

                if reraise:
                    raise
                return None

        return wrapper

    return decorator

`

### File: .\src\__init__.py
`python
# AMEVA Voice Screen Assistant — Source Package
__version__ = "0.1.0"

`

### File: .\src\input\audio_input.py
`python
"""
AMEVA Voice Screen Assistant — Audio Input
==========================================
Offline speech-to-text using a whisper.cpp binary.
"""

import logging
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("ameva.input")


class WhisperCppSTT:
    """
    Offline speech-to-text using a whisper.cpp binary.

    Flow: record mic → save WAV → run whisper.cpp → parse output text.
    """

    def __init__(self, cfg):
        self.cfg = cfg
        self.executable = cfg.get("stt", "whisper_executable", default="")
        self.model_path = cfg.get("stt", "whisper_model", default="")
        self.max_sec = cfg.get("stt", "recording_max_sec", default=30)

    def transcribe(self, wav_path: str = None) -> str:
        """
        Record (if no wav_path given) then transcribe.

        Returns the recognised text or raises on failure.
        """
        if not wav_path:
            wav_path = self._record()

        if not self.executable or not Path(self.executable).exists():
            raise FileNotFoundError(
                f"whisper.cpp executable not found: '{self.executable}'"
            )
        if not self.model_path or not Path(self.model_path).exists():
            raise FileNotFoundError(
                f"whisper model not found: '{self.model_path}'"
            )

        wav_path = str(wav_path)
        out_txt = wav_path + ".txt"

        cmd = [
            self.executable,
            "-m", str(self.model_path),
            "-f", wav_path,
            "--output-txt",
            "--no-prints",
        ]

        logger.info(f"Running whisper.cpp: {' '.join(cmd)}")
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"whisper.cpp failed (rc={result.returncode}): {result.stderr[:500]}"
            )

        # whisper.cpp writes {input}.txt
        txt_path = Path(out_txt)
        if not txt_path.exists():
            # Try without extension doubling
            alt = Path(wav_path).with_suffix(".txt")
            if alt.exists():
                txt_path = alt

        if txt_path.exists():
            text = txt_path.read_text(encoding="utf-8").strip()
            # Cleanup temp files
            try:
                txt_path.unlink()
            except OSError:
                pass
            return text

        # Fallback: parse stdout
        return result.stdout.strip()

    def _record(self) -> str:
        """Record from the default microphone and return the WAV path."""
        try:
            import sounddevice as sd
            import soundfile as sf
        except ImportError:
            raise RuntimeError(
                "sounddevice / soundfile not installed.  "
                "Run: pip install sounddevice soundfile"
            )

        sample_rate = 16000
        duration = min(self.max_sec, 30)

        logger.info(f"Recording for up to {duration}s at {sample_rate}Hz")
        audio = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
        )
        sd.wait()

        tmp_dir = Path(tempfile.gettempdir()) / "ameva_stt"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        wav_path = tmp_dir / f"rec_{ts}.wav"

        sf.write(str(wav_path), audio, sample_rate)
        logger.info(f"Recorded: {wav_path}")
        return str(wav_path)

`

### File: .\src\input\screen_capture.py
`python
"""
AMEVA Voice Screen Assistant — Screen Capture Module
=====================================================
Supports full-screen and per-monitor capture using ``mss`` (preferred)
with ``PIL.ImageGrab`` as fallback.

Captures are saved under ``data/captures/YYYYMMDD/cap_YYYYmmdd_HHMMSS_mmm.png``.
"""

import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("ameva.capture")


class ScreenCapture:
    """
    Screen capture handler.

    Parameters
    ----------
    cfg : AppConfig
        Runtime configuration (reads ``capture.root_dir``, ``capture.mode``, etc.)
    """

    def __init__(self, cfg):
        self.cfg = cfg

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def capture(self, mode: str = None, monitor_index: int = None) -> str:
        """
        Capture the screen and return the absolute file path.

        Parameters
        ----------
        mode : str, optional
            ``"full"`` or ``"monitor"``.  Defaults to config value.
        monitor_index : int, optional
            Monitor index (0-based) when ``mode="monitor"``.
        """
        mode = mode or self.cfg.get("capture", "mode", default="full")
        monitor_index = (
            monitor_index
            if monitor_index is not None
            else self.cfg.get("capture", "monitor_index", default=0)
        )

        out_path = self._make_output_path()

        if mode == "monitor":
            self._capture_monitor(monitor_index, out_path)
        else:
            self._capture_full(out_path)

        logger.info(f"Captured: {out_path}")
        return str(out_path)

    def list_monitors(self) -> list[dict]:
        """Return available monitors as a list of dicts with geometry info."""
        try:
            import mss

            with mss.mss() as sct:
                monitors = []
                # sct.monitors[0] is the virtual combined screen
                for i, m in enumerate(sct.monitors[1:], start=1):
                    monitors.append({
                        "index": i,
                        "left": m["left"],
                        "top": m["top"],
                        "width": m["width"],
                        "height": m["height"],
                    })
                return monitors
        except ImportError:
            logger.warning("mss not installed — monitor listing unavailable")
            return []

    # ------------------------------------------------------------------
    # Internal capture methods
    # ------------------------------------------------------------------
    def _capture_full(self, out_path: Path):
        """Full virtual-screen capture."""
        try:
            import mss
            import mss.tools

            with mss.mss() as sct:
                # monitors[0] = all monitors combined
                shot = sct.grab(sct.monitors[0])
                img = self._mss_to_pil(shot)
                img.save(str(out_path), "PNG")
                return
        except ImportError:
            pass

        # Fallback: Pillow ImageGrab
        from PIL import ImageGrab

        img = ImageGrab.grab(all_screens=True)
        img.save(str(out_path), "PNG")

    def _capture_monitor(self, index: int, out_path: Path):
        """Capture a specific monitor by index."""
        try:
            import mss

            with mss.mss() as sct:
                # index 1-based in mss (0 = virtual combined)
                real_index = index + 1
                if real_index >= len(sct.monitors):
                    logger.warning(
                        f"Monitor index {index} not found, falling back to full screen"
                    )
                    self._capture_full(out_path)
                    return
                shot = sct.grab(sct.monitors[real_index])
                img = self._mss_to_pil(shot)
                img.save(str(out_path), "PNG")
                return
        except ImportError:
            pass

        # Fallback: full screen
        logger.warning("mss not available — using full screen fallback")
        self._capture_full(out_path)

    @staticmethod
    def _mss_to_pil(shot):
        """Convert mss ScreenShot to PIL Image."""
        from PIL import Image

        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------
    def _make_output_path(self) -> Path:
        """Generate the output file path following the naming convention."""
        now = datetime.now()
        root = self.cfg.resolve_path(
            self.cfg.get("capture", "root_dir", default="data/captures")
        )
        day_dir = root / now.strftime("%Y%m%d")
        day_dir.mkdir(parents=True, exist_ok=True)

        filename = now.strftime("cap_%Y%m%d_%H%M%S_") + f"{now.microsecond // 1000:03d}.png"
        return day_dir / filename

`

### File: .\src\orchestration\router.py
`python
"""
AMEVA Voice Screen Assistant — Fallback Router
================================================
Evaluates job contexts and OCR outputs to determine whether a query should
be routed to the Text LLM (primary) or escalate to a local VLM (fallback).
Supports Fast-track (intent-based) and Retry-based (failure-based) routing.
"""

import logging

logger = logging.getLogger("ameva.router")

# Affordance keywords that indicate a strictly visual query
AFFORDANCE_KEYWORDS = [
    "어디", "버튼", "아이콘", "모양", "색깔", "그림", "눌러", "위치"
]

# Phrases that indicate the Text LLM failed to understand the screen
FAILURE_PHRASES = [
    "정확히 판단하기 어렵다",
    "알 수 없다",
    "ocr 결과가 불명확하다"
]

class FallbackRouter:
    """
    Decides routing between OCR-first (Text LLM) and Multimodal Fallback (VLM).
    """

    @staticmethod
    def should_fast_track_to_vlm(input_text: str) -> bool:
        """
        Check if the user intent mandates a direct visual approach,
        bypassing the OCR-first path entirely.
        """
        text_lower = input_text.lower()
        for kw in AFFORDANCE_KEYWORDS:
            if kw in text_lower:
                logger.info(f"[Router] Fast-track to VLM triggered by keyword: '{kw}'")
                return True
        return False

    @staticmethod
    def should_fallback_based_on_ocr(ocr_blocks: list) -> bool:
        """
        Check if the OCR quality is too poor, warranting a VLM fallback.
        Thresholds are based on Phase 3 defaults.
        """
        block_count = len(ocr_blocks)
        if block_count < 5:
            logger.info(f"[Router] Fallback triggered: Low OCR block count ({block_count} < 5)")
            return True
            
        total_chars = sum(len(b.get("text", "")) for b in ocr_blocks)
        if total_chars < 20:
            logger.info(f"[Router] Fallback triggered: Low total OCR chars ({total_chars} < 20)")
            return True
            
        avg_conf = sum(b.get("confidence", 0) for b in ocr_blocks) / block_count
        if avg_conf < 0.55:
            logger.info(f"[Router] Fallback triggered: Low average OCR confidence ({avg_conf:.2f} < 0.55)")
            return True

        return False

    @staticmethod
    def should_fallback_based_on_scene_graph(scene_graph: dict) -> bool:
        """
        Check if the scene graph heuristic failed to classify the screen type.
        """
        stype = scene_graph.get("screen_type", "unknown_application")
        if stype == "unknown_application":
            logger.info("[Router] Fallback triggered: Scene graph screen_type classification failed")
            return True
        return False

    @staticmethod
    def should_fallback_based_on_llm_failure(llm_response: str) -> bool:
        """
        Check if the 1st tier Text LLM explicitly admitted failure due to poor context.
        """
        resp_lower = llm_response.lower()
        for phrase in FAILURE_PHRASES:
            if phrase in resp_lower:
                logger.info(f"[Router] Fallback triggered: LLM failure phrase detected '{phrase}'")
                return True
        return False

`

### File: .\src\orchestration\worker.py
`python
"""
AMEVA Voice Screen Assistant — Worker Thread
=============================================
Background daemon thread that consumes jobs from a ``queue.Queue``,
runs the inference pipeline (capture → OCR → semantic → prompt → LLM → save → emit), 
and pushes results back to the UI via a result queue.
"""

import logging
import queue
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("ameva.orchestration.worker")

# Sentinel object to signal the worker to shut down
_SHUTDOWN = object()


@dataclass
class Job:
    job_id: int
    session_id: str
    input_text: str
    inp_mode: str = "text"          # "text" | "voice"
    capture_path: str | None = None
    tts_enabled: bool = False
    
    # Capture spec
    capture_mode: str = "full"
    monitor_index: int = 0
    
    # Fallback tracking
    semantic_fallback_used: bool = False
    backend_retry_count: int = 0
    
    # populated after completion
    result_text: str | None = None
    error_msg: str | None = None
    latency_ms: int = 0
    extra: dict = field(default_factory=dict)


@dataclass
class WorkerResult:
    job: Job
    success: bool
    llm_provider: str = ""
    llm_model: str = ""


class WorkerThread(threading.Thread):
    def __init__(self, job_queue, result_queue, db, cfg):
        super().__init__(daemon=True, name="ameva-worker")
        self.job_queue = job_queue
        self.result_queue = result_queue
        self.db = db
        self.cfg = cfg
        
        # Lazy init providers
        self._llm = None
        self._tts = None
        self._ocr = None
        self._semantic = None
        self._prompt_builder = None

    def _get_ocr(self):
        if self._ocr is None:
            try:
                from src.perception.ocr.tesseract_provider import TesseractProvider
                self._ocr = TesseractProvider(self.cfg)
            except Exception as e:
                logger.warning(f"OCR provider unavailable: {e}")
        return self._ocr

    def _get_semantic(self):
        if self._semantic is None:
            from src.semantic.scene_graph_builder import SceneGraphBuilder
            self._semantic = SceneGraphBuilder(self.cfg)
        return self._semantic

    def _get_prompt_builder(self):
        if self._prompt_builder is None:
            from src.reasoning.prompt_builder import PromptBuilder
            self._prompt_builder = PromptBuilder(self.cfg, self.db)
        return self._prompt_builder

    def _get_llm(self):
        if self._llm is None:
            try:
                from src.reasoning.llm_client import LlamaCppOpenAICompat
                self._llm = LlamaCppOpenAICompat(self.cfg)
            except Exception:
                logger.warning("LLM provider unavailable, using DummyLLM")
                from src.reasoning.llm_client import DummyLLM
                self._llm = DummyLLM()
        return self._llm

    def _get_tts(self):
        if self._tts is None:
            try:
                from src.output.tts_client import WindowsSAPITTS
                self._tts = WindowsSAPITTS()
            except Exception:
                logger.warning("TTS provider unavailable", exc_info=True)
        return self._tts

    def run(self):
        logger.info("Worker thread started")
        while True:
            try:
                job = self.job_queue.get()
                if job is _SHUTDOWN:
                    logger.info("Worker received shutdown signal")
                    break

                self._process_job(job)
            except Exception:
                logger.error("Worker loop error", exc_info=True)

        logger.info("Worker thread stopped")

    def _process_job(self, job: Job):
        logger.info(f"Processing job {job.job_id} (mode={job.inp_mode})")
        self.db.update_job_state(job.job_id, "running")

        stage = "init"
        try:
            # 1. Capture
            stage = "capture"
            if job.capture_path is None and self.cfg.get("capture", "auto_capture", default=True):
                try:
                    from src.input.screen_capture import ScreenCapture
                    sc = ScreenCapture(self.cfg)
                    job.capture_path = sc.capture(mode=job.capture_mode, monitor_index=job.monitor_index)
                except Exception as e:
                    logger.warning(f"Capture failed: {e}", exc_info=True)
                    
            from src.orchestration.router import FallbackRouter
            from src.reasoning.vlm_client import VLMClient

            fast_track = FallbackRouter.should_fast_track_to_vlm(job.input_text)

            # 2. OCR Extraction
            stage = "ocr"
            ocr_data = {}
            if job.capture_path:
                ocr = self._get_ocr()
                if ocr:
                    try:
                        ocr_data = ocr.extract_text_blocks(job.capture_path)
                        job.extra["ocr_raw"] = ocr_data.get("raw_blocks", []) # before post-process
                        job.extra["ocr_cleaned"] = ocr_data.get("blocks", [])
                    except Exception as e:
                        logger.warning(f"OCR failed: {e}", exc_info=True)
            
            # 3. Semantic Normalization
            stage = "semantic"
            semantic_summary = ""
            if ocr_data:
                semantic_builder = self._get_semantic()
                scene_graph, semantic_summary = semantic_builder.build(ocr_data, job.input_text)
                # We could save scene_graph to job.extra or db here
                job.extra["scene_graph"] = scene_graph

            # Fallback checking
            ocr_fallback = False
            sg_fallback = False
            if ocr_data:
                ocr_fallback = FallbackRouter.should_fallback_based_on_ocr(ocr_data.get("blocks", []))
                if job.extra.get("scene_graph"):
                    sg_fallback = FallbackRouter.should_fallback_based_on_scene_graph(job.extra["scene_graph"])

            should_fallback = (fast_track or ocr_fallback or sg_fallback)
            llm_prov = "Unknown"

            # 4. Prompt Build
            stage = "prompt"
            pb = self._get_prompt_builder()
            messages = pb.build_messages(job.session_id, job.capture_path, semantic_summary)

            # 5. LLM Call
            stage = "llm"
            job.extra["prompt"] = messages
            
            # Helper to run VLM
            def run_vlm_fallback():
                job.semantic_fallback_used = True
                logger.info(f"Routing job {job.job_id} to VLM (Fast-track={fast_track}, OCR={ocr_fallback}, SG={sg_fallback})")
                vlm = VLMClient(self.cfg)
                while job.backend_retry_count < 3:
                    try:
                        t0 = time.perf_counter()
                        r_text = vlm.ask_image(job.capture_path, job.input_text)
                        job.latency_ms = int((time.perf_counter() - t0) * 1000)
                        return r_text, vlm.adapter.__class__.__name__
                    except Exception as e:
                        job.backend_retry_count += 1
                        logger.warning(f"VLM backend failed (retry {job.backend_retry_count}/3): {e}")
                        time.sleep(1)
                
                logger.error("VLM failed after 3 retries. Degraded response.")
                return '{"status": "local_vlm_unavailable", "message": "Failed to connect to local VLM"}', "FallbackFailed"

            if should_fallback and not job.semantic_fallback_used:
                response_text, llm_prov = run_vlm_fallback()
            else:
                llm = self._get_llm()
                llm_prov = type(llm).__name__
                t0 = time.perf_counter()
                response_text = llm.generate(messages)
                job.latency_ms = int((time.perf_counter() - t0) * 1000)
                
                # Retry-based LLM failure check
                if FallbackRouter.should_fallback_based_on_llm_failure(response_text) and not job.semantic_fallback_used:
                    logger.info("Text LLM returned a failure response. Triggering VLM fallback!")
                    response_text, llm_prov = run_vlm_fallback()

            job.result_text = response_text
            job.extra["llm_response"] = response_text
            
            # Save artifacts for debugging
            try:
                import os, json
                art_dir = os.path.join(self.cfg.get("app", "data_dir", default="data"), "artifacts")
                os.makedirs(art_dir, exist_ok=True)
                art_file = os.path.join(art_dir, f"job_{job.job_id}_artifacts.json")
                with open(art_file, "w", encoding="utf-8") as f:
                    json.dump(job.extra, f, ensure_ascii=False, indent=2)
            except Exception as art_e:
                logger.warning(f"Failed to save artifacts: {art_e}")

            # 6. Response Save
            stage = "save"
            if llm_prov not in ["LocalMockMultimodalAdapter", "LocalLlamaCppMultimodalAdapter", "FallbackFailed"]:
                llm_mdl = self.cfg.get("llm", "model_alias", default="local-gguf")
            else:
                llm_mdl = "vlm-fallback"

            self.db.insert_message(
                sess_id=job.session_id,
                role="assistant",
                content=response_text,
                cap_path=job.capture_path,
                llm_prov=llm_prov,
                llm_mdl=llm_mdl,
                tts_enbl=job.tts_enabled,
                ltncy_ms=job.latency_ms,
            )

            # (Optional) TTS
            stage = "tts"
            if job.tts_enabled:
                tts = self._get_tts()
                if tts is not None:
                    try:
                        tts.speak(response_text)
                    except Exception as e:
                        logger.warning(f"TTS failed (non-fatal): {e}")

            # 7. UI Emit
            stage = "emit"
            self.db.update_job_state(job.job_id, "done")
            self.db.update_session_active(job.session_id)

            self.result_queue.put(
                WorkerResult(job=job, success=True, llm_provider=llm_prov, llm_model=llm_mdl)
            )
            logger.info(f"Job {job.job_id} completed ({job.latency_ms}ms)")

        except Exception as e:
            tb_str = traceback.format_exc()
            job.error_msg = f"[{stage} stage] {str(e)}"
            logger.error(f"Job {job.job_id} failed at {stage}: {e}", exc_info=True)

            err_id = self.db.insert_log(
                level="ERROR",
                message=f"[worker:{stage}] Job {job.job_id}: {e}",
                tb=tb_str,
            )
            self.db.update_job_state(job.job_id, "error", err_id=err_id)

            self.result_queue.put(WorkerResult(job=job, success=False))

    def request_shutdown(self):
        """Signal the worker to stop after finishing the current job."""
        self.job_queue.put(_SHUTDOWN)

SHUTDOWN_SENTINEL = _SHUTDOWN

`

### File: .\src\output\tts_client.py
`python
"""
AMEVA Voice Screen Assistant — TTS Client
=========================================
Non-blocking text-to-speech using Windows SAPI through PowerShell.
"""

import logging
import subprocess

logger = logging.getLogger("ameva.output")


class WindowsSAPITTS:
    """
    Non-blocking text-to-speech using Windows SAPI through PowerShell.

    Runs in a subprocess so it never blocks the UI or worker thread
    for longer than the subprocess launch time.
    """

    def speak(self, text: str, **kwargs):
        """Speak the given text.  Non-fatal — logs errors but never raises."""
        if not text or not text.strip():
            return

        # Escape single quotes for PowerShell
        safe_text = text.replace("'", "''")
        # Limit length to prevent very long speech
        if len(safe_text) > 2000:
            safe_text = safe_text[:2000]

        ps_cmd = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Speak('{safe_text}')"
        )

        try:
            subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            logger.debug("TTS speak dispatched")
        except Exception as e:
            logger.warning(f"TTS failed: {e}")

`

### File: .\src\perception\ocr\ocr_interface.py
`python
"""
AMEVA Voice Screen Assistant — OCR Interface
============================================
Defines the standard interface for OCR providers.
"""

from typing import Any, Protocol


class OCRProvider(Protocol):
    """Protocol for OCR engines."""

    def extract_text_blocks(self, image_path: str) -> dict[str, Any]:
        """
        Extract text from an image.

        Returns a dictionary matching the schema:
        {
            "engine": str,
            "image_path": str,
            "blocks": [
                {
                    "text": str,
                    "bbox": [x1, y1, x2, y2],
                    "confidence": float
                },
                ...
            ]
        }
        """
        ...

`

### File: .\src\perception\ocr\postprocessor.py
`python
"""
AMEVA Voice Screen Assistant — OCR Post-processor
=================================================
Cleans, filters, and merges raw OCR bounding boxes to reduce noise and
improve semantic grouping (e.g. combining words on the same line).
"""

import logging
from typing import Any

logger = logging.getLogger("ameva.perception.ocr.postprocessor")


class OCRPostProcessor:
    """Post-processes raw OCR bounding boxes."""

    def __init__(self, min_confidence: float = 0.3, max_x_gap_multiplier: float = 1.5, max_y_diff_multiplier: float = 0.5):
        """
        Args:
            min_confidence: Ignore blocks with confidence below this threshold (0.0 to 1.0)
            max_x_gap_multiplier: Max horizontal gap between boxes to merge, as a multiple of box height.
            max_y_diff_multiplier: Max vertical difference between tops to consider them on the same line.
        """
        self.min_confidence = min_confidence
        self.max_x_gap_multiplier = max_x_gap_multiplier
        self.max_y_diff_multiplier = max_y_diff_multiplier

    def process(self, raw_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Filters and merges raw blocks.
        Raw block schema: {"text": str, "bbox": [x1, y1, x2, y2], "confidence": float}
        """
        # 1. Filter out noise and empty text
        import re
        valid_blocks = []
        for b in raw_blocks:
            text = b.get("text", "").strip()
            conf = b.get("confidence", 0.0)
            
            # Short noise token removal (1 char or special character junk)
            if len(text) <= 1 and not text.isalnum():
                continue
            if re.match(r"^[^a-zA-Z0-9가-힣]+$", text): # Only symbols
                continue
                
            if text and conf >= self.min_confidence:
                valid_blocks.append(b)

        if not valid_blocks:
            return []

        # 2. Sort by Y (top) then X (left)
        valid_blocks.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))

        # 3. Merge adjacent blocks on the same line
        merged_blocks = []
        current_block = valid_blocks[0].copy()

        for next_block in valid_blocks[1:]:
            c_x1, c_y1, c_x2, c_y2 = current_block["bbox"]
            n_x1, n_y1, n_x2, n_y2 = next_block["bbox"]

            c_height = c_y2 - c_y1
            n_height = n_y2 - n_y1
            avg_height = (c_height + n_height) / 2.0

            y_diff = abs(c_y1 - n_y1)
            x_gap = n_x1 - c_x2

            # Check if they are on the same line and close enough horizontally
            same_line = y_diff < (avg_height * self.max_y_diff_multiplier)
            # x_gap can be slightly negative if boxes overlap
            close_horizontally = x_gap < (avg_height * self.max_x_gap_multiplier)

            if same_line and close_horizontally:
                # Merge next_block into current_block
                current_block["text"] += " " + next_block["text"]
                current_block["bbox"] = [
                    min(c_x1, n_x1),
                    min(c_y1, n_y1),
                    max(c_x2, n_x2),
                    max(c_y2, n_y2)
                ]
                # Average confidence (weighted by text length could be better, but simple average is fine)
                current_block["confidence"] = round((current_block["confidence"] + next_block["confidence"]) / 2.0, 3)
            else:
                # Push current and start new
                merged_blocks.append(current_block)
                current_block = next_block.copy()

        # Push the last block
        if current_block:
            merged_blocks.append(current_block)

        return merged_blocks

`

### File: .\src\perception\ocr\tesseract_provider.py
`python
"""
AMEVA Voice Screen Assistant — Tesseract OCR Provider
=====================================================
Uses pytesseract to extract text and bounding boxes from images.
Requires Tesseract OCR OS-level installation.
"""

import logging
from typing import Any

import pytesseract
from PIL import Image

from src.perception.ocr.postprocessor import OCRPostProcessor

logger = logging.getLogger("ameva.perception.ocr")


class TesseractProvider:
    """Tesseract OCR implementation."""

    def __init__(self, cfg):
        self.cfg = cfg
        tess_cmd = self.cfg.get("ocr", "tesseract_cmd", default="")
        if not tess_cmd:
            import os
            default_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(default_path):
                tess_cmd = default_path
                
        if tess_cmd:
            pytesseract.pytesseract.tesseract_cmd = tess_cmd
        
        self.lang = self.cfg.get("ocr", "lang", default="kor+eng")

    def extract_text_blocks(self, image_path: str) -> dict[str, Any]:
        """Extract text blocks using pytesseract.image_to_data."""
        logger.info(f"Running Tesseract OCR on {image_path}")
        
        try:
            img = Image.open(image_path)
            img_w, img_h = img.size
            data = pytesseract.image_to_data(img, lang=self.lang, output_type=pytesseract.Output.DICT)
            
            blocks = []
            n_boxes = len(data['level'])
            
            for i in range(n_boxes):
                text = data['text'][i].strip()
                # Ignore empty text blocks and low confidence blocks (e.g., < 30)
                conf = float(data['conf'][i])
                if text and conf > 30:
                    x1 = data['left'][i]
                    y1 = data['top'][i]
                    w = data['width'][i]
                    h = data['height'][i]
                    x2 = x1 + w
                    y2 = y1 + h
                    
                    blocks.append({
                        "text": text,
                        "bbox": [x1, y1, x2, y2],
                        "confidence": round(conf / 100.0, 3) # Normalize to 0-1
                    })
                    
            # Post-process the raw blocks
            postprocessor = OCRPostProcessor(min_confidence=0.3)
            processed_blocks = postprocessor.process(blocks)
                    
            return {
                "engine": "tesseract",
                "image_path": str(image_path),
                "resolution": {"width": img_w, "height": img_h},
                "blocks": processed_blocks,
                "raw_blocks": blocks
            }
            
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            raise RuntimeError(f"OCR failed: {e}") from e

`

### File: .\src\reasoning\llm_client.py
`python
"""
AMEVA Voice Screen Assistant — LLM Client
==========================================
Talks to a llama.cpp ``llama-server`` via its OpenAI-compatible API.
"""

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger("ameva.reasoning")


class BaseLLM:
    """Abstract LLM provider interface."""

    def health_check(self) -> bool:
        raise NotImplementedError

    def generate(self, messages: list[dict], **kwargs) -> str:
        raise NotImplementedError


class LlamaCppOpenAICompat(BaseLLM):
    """
    Talks to a llama.cpp ``llama-server`` via its OpenAI-compatible API.

    Endpoints used:
      - ``GET  /v1/models``            — health / model info
      - ``POST /v1/chat/completions``  — chat generation
    """

    def __init__(self, cfg):
        self.cfg = cfg
        self.base_url = cfg.get("llm", "base_url", default="http://127.0.0.1:8080/v1")
        self.model_alias = cfg.get("llm", "model_alias", default="local-gguf")
        self.temperature = cfg.get("llm", "temperature", default=0.2)
        self.max_tokens = cfg.get("llm", "max_tokens", default=512)
        self.timeout = cfg.get("llm", "timeout_sec", default=60)

    def health_check(self) -> bool:
        """``GET /models`` — returns True if the server is alive."""
        url = f"{self.base_url}/models"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"LLM health check failed: {e}")
            return False

    def generate(self, messages: list[dict], **kwargs) -> str:
        """
        ``POST /chat/completions`` — send messages and return the
        assistant's reply text.

        Raises on network / parse errors so the worker can log them.
        """
        # Reload settings in case they changed at runtime
        self.base_url = self.cfg.get("llm", "base_url", default=self.base_url)
        self.model_alias = self.cfg.get("llm", "model_alias", default=self.model_alias)

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model_alias,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "frequency_penalty": 1.15,
            "presence_penalty": 0.1,
            "stream": False,
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.URLError as e:
            raise ConnectionError(f"LLM server unreachable: {e}") from e
        except TimeoutError:
            raise TimeoutError(f"LLM request timed out ({self.timeout}s)")

        try:
            result = json.loads(body)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM returned invalid JSON: {body[:200]}") from e

        # Extract reply
        try:
            return result["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise ValueError(f"Unexpected LLM response structure: {result}") from e


class DummyLLM(BaseLLM):
    """Echoes the last user message.  Useful for UI/queue testing."""

    def __init__(self, delay_sec: float = 1.0):
        self.delay_sec = delay_sec

    def health_check(self) -> bool:
        return True

    def generate(self, messages: list[dict], **kwargs) -> str:
        time.sleep(self.delay_sec)
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content", "")
                break
        return f"[DummyLLM echo] {last_user}"

`

### File: .\src\reasoning\prompt_builder.py
`python
"""
AMEVA Voice Screen Assistant — Prompt Builder
=============================================
Constructs the context and message history for the LLM.
"""

import logging

logger = logging.getLogger("ameva.reasoning")


class PromptBuilder:
    """Builds the message array for the LLM API call."""

    def __init__(self, cfg, db):
        self.cfg = cfg
        self.db = db

    def build_messages(self, job_session_id: str, job_capture_path: str, semantic_summary: str = "") -> list[dict]:
        """
        Builds the conversation context. In Phase 1, it injects the OCR semantic summary
        into the system or user prompt so the text LLM has screen context.
        """
        base_prompt = self.cfg.get(
            "llm", "system_prompt",
            default="You are a helpful desktop assistant."
        )
        
        # Override with strict hallucination prevention rules as requested in Phase 2
        strict_rules = (
            "You are a precise screen analysis AI.\n"
            "CRITICAL RULES:\n"
            "1. 너는 OCR 및 scene graph 결과만을 근거로 답변해야 한다.\n"
            "2. 근거가 부족하면 추측하지 말고 '정확히 판단하기 어렵다'고 답하라.\n"
            "3. 깨진 문자열이나 의미 없는 토큰에 임의의 뜻을 부여하지 말라.\n"
            "4. 확실한 근거가 있는 경우에만 화면 유형이나 기능을 설명하라.\n"
            "5. 사용자의 질문과 관련된 정보만 우선 사용하라.\n"
            "6. 확실한 경우는 근거를 제시, 애매하면 '~처럼 보인다'로 추정, 판단 불가면 '판단 어렵다'고 명시하라."
        )
        system_prompt = f"{base_prompt}\n\n{strict_rules}"

        messages = [{"role": "system", "content": system_prompt}]

        # Load recent conversation history from this session
        history = self.db.get_messages(job_session_id)
        for msg in history[-20:]:  # last 20 messages for context window
            messages.append({"role": msg["role"], "content": msg["content"]})

        # Inject semantic summary if available
        if semantic_summary:
            ctx_note = f"\n\n[Screen Context from OCR]:\n{semantic_summary}"
            # Append context note to the last user message
            if messages and messages[-1]["role"] == "user":
                messages[-1]["content"] += ctx_note

        # If there's a capture but no semantic summary, just mention it
        elif job_capture_path:
            ctx_note = f"\n\n[Screen capture saved: {job_capture_path}]"
            if messages and messages[-1]["role"] == "user":
                messages[-1]["content"] += ctx_note

        return messages

`

### File: .\src\reasoning\vlm_client.py
`python
"""
AMEVA Voice Screen Assistant — Strictly Local Multimodal VLM Client
=====================================================================
Client for Vision Language Models (VLM).
Strictly adheres to local/offline only. External APIs, network uploads,
and cloud inference are explicitly prohibited by architecture rules.
"""

import json
import logging
import base64
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

logger = logging.getLogger("ameva.vlm")

class LocalMultimodalAdapter:
    """Base interface for local multimodal adapters."""
    def generate(self, image_path: str, prompt: str, **kwargs) -> str:
        raise NotImplementedError()

class LocalMockMultimodalAdapter(LocalMultimodalAdapter):
    """
    Mock adapter for when a real local VLM is not available.
    Returns a structured fallback-unavailable response.
    """
    def generate(self, image_path: str, prompt: str, **kwargs) -> str:
        logger.info(f"[LocalMockVLM] Received multimodal request for image: {image_path}")
        return (
            "{\n"
            '  "status": "local_vlm_unavailable",\n'
            '  "message": "Local multimodal backend is not configured or offline. Fallback aborted.",\n'
            f'  "mock_received_prompt": "{prompt[:50]}..."\n'
            "}"
        )

class LocalLlamaCppMultimodalAdapter(LocalMultimodalAdapter):
    """
    Adapter for local llama.cpp server running with an mmproj model.
    Sends base64 encoded image directly to localhost.
    """
    def __init__(self, endpoint_url: str = "http://127.0.0.1:8080/v1/chat/completions"):
        self.endpoint_url = endpoint_url
        
    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')

    def generate(self, image_path: str, prompt: str, **kwargs) -> str:
        try:
            base64_image = self._encode_image(image_path)
            
            # Llama.cpp multimodal OpenAI-compatible payload
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
            
            payload = {
                "messages": messages,
                "temperature": kwargs.get("temperature", 0.1),
                "max_tokens": kwargs.get("max_tokens", 512)
            }
            
            req = urllib.request.Request(
                self.endpoint_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            
            with urllib.request.urlopen(req, timeout=120) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
                return resp_data["choices"][0]["message"]["content"].strip()
                
        except urllib.error.URLError as e:
            logger.error(f"Local VLM connection failed: {e}")
            raise ConnectionError(f"Failed to connect to local VLM: {e}")
        except Exception as e:
            logger.error(f"Local VLM error: {e}")
            raise


class VLMClient:
    """
    High-level client for multimodal reasoning.
    Strictly restricted to load only LocalMultimodalAdapters.
    """
    def __init__(self, cfg):
        self.cfg = cfg
        self.provider_name = self.cfg.get("vlm", "provider", default="mock").lower()
        
        if self.provider_name == "llama_cpp":
            self.adapter = LocalLlamaCppMultimodalAdapter(
                endpoint_url=self.cfg.get("vlm", "endpoint", default="http://127.0.0.1:8081/v1/chat/completions")
            )
        else:
            self.adapter = LocalMockMultimodalAdapter()
            
    def ask_image(self, image_path: str, prompt: str, **kwargs) -> str:
        """Process an image and text prompt using the configured local VLM."""
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
            
        logger.info(f"VLM reasoning invoked using adapter: {self.adapter.__class__.__name__}")
        return self.adapter.generate(image_path, prompt, **kwargs)

`

### File: .\src\semantic\scene_graph_builder.py
`python
"""
AMEVA Voice Screen Assistant — Scene Graph Builder
==================================================
Transforms raw OCR text blocks into a structured scene representation
and a text summary for the reasoning layer.
"""

import json
import logging
from typing import Any

logger = logging.getLogger("ameva.semantic")


class SceneGraphBuilder:
    """Builds semantic understanding from perception output."""

    def __init__(self, cfg):
        self.cfg = cfg

    def build(self, ocr_data: dict[str, Any], user_question: str = "") -> tuple[dict[str, Any], str]:
        """
        Builds the scene graph and text summary.
        
        Returns:
            A tuple of (scene_graph_json, text_summary)
        """
        blocks = ocr_data.get("blocks", [])
        resolution = ocr_data.get("resolution", {"width": 1920, "height": 1080})
        img_w, img_h = resolution["width"], resolution["height"]
        
        # Analyze question relevance
        q = user_question.lower()
        rel_toolbar = any(k in q for k in ["그림", "도구", "버튼", "draw", "tool", "button"])
        rel_sidebar = any(k in q for k in ["파일", "목록", "탐색", "file", "explorer", "sidebar"])
        rel_status = any(k in q for k in ["상태", "메모리", "cpu", "status"])
        # Body is generally always relevant, but highly relevant for logs/text
        
        regions = {
            "toolbar": [],
            "sidebar": [],
            "body": [],
            "status_bar": []
        }
        
        for b in blocks:
            text = b.get("text", "")
            if not text:
                continue
                
            x1, y1, x2, y2 = b.get("bbox")
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            
            # Simple heuristic classification for role
            r_type = "text"
            text_lower = text.lower()
            
            if "error" in text_lower or "exception" in text_lower or "fail" in text_lower:
                r_type = "log"
            elif len(text) < 15 and ("ok" in text_lower or "cancel" in text_lower or "retry" in text_lower or "submit" in text_lower):
                r_type = "button"
            elif len(text) < 30 and text.isupper():
                r_type = "title"
                
            item = {
                "role": r_type,
                "bbox": b.get("bbox"),
                "text": text,
                "confidence": b.get("confidence")
            }
            
            # Layout heuristic
            if cy < img_h * 0.15:
                regions["toolbar"].append(item)
            elif cy > img_h * 0.95:
                regions["status_bar"].append(item)
            elif cx < img_w * 0.25:
                regions["sidebar"].append(item)
            else:
                regions["body"].append(item)

        scene_graph = {
            "screen_type": "unknown_application",
            "resolution": resolution,
            "regions": regions
        }
        
        # Build compressed text summary for prompt
        lines = []
        for region_name, items in regions.items():
            if not items:
                continue
            
            # Relevance compression
            is_relevant = True
            if region_name == "toolbar" and not rel_toolbar and len(items) > 5:
                is_relevant = False
            elif region_name == "sidebar" and not rel_sidebar and len(items) > 5:
                is_relevant = False
            elif region_name == "status_bar" and not rel_status and len(items) > 3:
                is_relevant = False
                
            if is_relevant:
                lines.append(f"--- [REGION: {region_name.upper()}] ---")
                for r in items:
                    lines.append(f"[{r['role'].upper()}] {r['text']}")
            else:
                lines.append(f"--- [REGION: {region_name.upper()}] ({len(items)} items hidden) ---")
            
        summary = "\n".join(lines)
        if not summary:
            summary = "No readable text found on the screen."
            
        return scene_graph, summary

`

### File: .\src\storage\db.py
`python
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

`

### File: .\src\ui\ui_main.py
`python
"""
AMEVA Voice Screen Assistant — Main Tkinter UI
================================================
Dual-panel chat interface with session list, chat log, input area,
status bar with spinner/animation, and mic button for voice input.

All long-running operations happen in the worker thread.  The UI
polls ``result_queue`` via ``after()`` and never blocks.
"""

import logging
import os
import queue
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

from src.orchestration.worker import WorkerThread, Job, WorkerResult

logger = logging.getLogger("ameva.ui")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_POLL_MS = 100          # result queue polling interval
_ANIM_MS = 300          # spinner / dots animation interval
_SPINNER = ["|", "/", "—", "\\"]
_DOTS = ["", ".", "..", "..."]

# Color palette
_CLR_BG        = "#1e1e2e"
_CLR_BG_LIGHT  = "#2a2a3d"
_CLR_FG        = "#cdd6f4"
_CLR_USER      = "#89b4fa"
_CLR_ASST      = "#a6e3a1"
_CLR_SYSTEM    = "#6c7086"
_CLR_ERROR     = "#f38ba8"
_CLR_ACCENT    = "#cba6f7"
_CLR_ENTRY_BG  = "#313244"
_CLR_BTN       = "#45475a"
_CLR_BTN_HOVER = "#585b70"
_CLR_MIC_REC   = "#f38ba8"
_CLR_LINK      = "#74c7ec"


# ---------------------------------------------------------------------------
# MainWindow
# ---------------------------------------------------------------------------
class MainWindow(tk.Tk):
    """
    Top-level Tkinter window hosting the full assistant UI.

    Parameters
    ----------
    db : DatabaseManager
    cfg : AppConfig
    """

    def __init__(self, db, cfg):
        super().__init__()

        self.db = db
        self.cfg = cfg

        # State
        self._current_session_id: str | None = None
        self._is_running = False
        self._spinner_idx = 0
        self._dots_idx = 0
        self._recording = False

        # Queues
        self._job_queue: queue.Queue = queue.Queue()
        self._result_queue: queue.Queue = queue.Queue()

        # Worker
        self._worker = WorkerThread(
            self._job_queue, self._result_queue, self.db, self.cfg
        )
        self._worker.start()

        # Window config
        self.title("AMEVA Voice Screen Assistant")
        self.geometry("1100x720")
        self.minsize(800, 500)
        self.configure(bg=_CLR_BG)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Build UI
        self._build_ui()
        self._load_sessions()

        # Start polling loops
        self._poll_results()
        self._animate_status()

    # ==================================================================
    #  UI Construction
    # ==================================================================
    def _build_ui(self):
        # --- Main horizontal paned window ---
        paned = tk.PanedWindow(
            self, orient=tk.HORIZONTAL, bg=_CLR_BG,
            sashwidth=3, sashrelief=tk.FLAT,
        )
        paned.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Left: Session panel
        self._left_frame = tk.Frame(paned, bg=_CLR_BG_LIGHT, width=240)
        paned.add(self._left_frame, minsize=180)
        self._build_session_panel(self._left_frame)

        # Right: Chat + Input + Status
        self._right_frame = tk.Frame(paned, bg=_CLR_BG)
        paned.add(self._right_frame, minsize=500)
        self._build_chat_panel(self._right_frame)
        self._build_input_panel(self._right_frame)
        self._build_status_bar(self._right_frame)

    # ------------------------------------------------------------------
    # Session panel (Left)
    # ------------------------------------------------------------------
    def _build_session_panel(self, parent):
        header = tk.Frame(parent, bg=_CLR_BG_LIGHT)
        header.pack(fill=tk.X, padx=8, pady=(8, 4))

        tk.Label(
            header, text="세션 목록", font=("Segoe UI", 11, "bold"),
            bg=_CLR_BG_LIGHT, fg=_CLR_ACCENT,
        ).pack(side=tk.LEFT)

        btn_new = tk.Button(
            header, text="＋ 새 세션", font=("Segoe UI", 9),
            bg=_CLR_BTN, fg=_CLR_FG, relief=tk.FLAT, cursor="hand2",
            activebackground=_CLR_BTN_HOVER, activeforeground=_CLR_FG,
            command=self._on_new_session,
        )
        btn_new.pack(side=tk.RIGHT)

        self._session_listbox = tk.Listbox(
            parent, font=("Segoe UI", 10), bg=_CLR_BG_LIGHT,
            fg=_CLR_FG, selectbackground=_CLR_ACCENT,
            selectforeground=_CLR_BG, relief=tk.FLAT,
            activestyle="none", borderwidth=0, highlightthickness=0,
        )
        self._session_listbox.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self._session_listbox.bind("<<ListboxSelect>>", self._on_session_select)

        # Internal mapping: listbox index → session id
        self._session_ids: list[str] = []

    # ------------------------------------------------------------------
    # Chat panel (Center)
    # ------------------------------------------------------------------
    def _build_chat_panel(self, parent):
        chat_frame = tk.Frame(parent, bg=_CLR_BG)
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))

        self._chat_text = tk.Text(
            chat_frame, wrap=tk.WORD, state=tk.DISABLED,
            bg=_CLR_BG, fg=_CLR_FG, font=("Segoe UI", 10),
            relief=tk.FLAT, borderwidth=0, padx=12, pady=8,
            insertbackground=_CLR_FG, selectbackground=_CLR_ACCENT,
            cursor="arrow",
        )
        scrollbar = ttk.Scrollbar(chat_frame, command=self._chat_text.yview)
        self._chat_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._chat_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Tag styles
        self._chat_text.tag_configure("user", foreground=_CLR_USER, font=("Segoe UI", 10, "bold"))
        self._chat_text.tag_configure("assistant", foreground=_CLR_ASST)
        self._chat_text.tag_configure("system", foreground=_CLR_SYSTEM, font=("Segoe UI", 9, "italic"))
        self._chat_text.tag_configure("error", foreground=_CLR_ERROR)
        self._chat_text.tag_configure("meta", foreground=_CLR_SYSTEM, font=("Segoe UI", 8))
        self._chat_text.tag_configure("link", foreground=_CLR_LINK, underline=True)
        self._chat_text.tag_bind("link", "<Button-1>", self._on_link_click)
        self._chat_text.tag_bind("link", "<Enter>", lambda e: self._chat_text.configure(cursor="hand2"))
        self._chat_text.tag_bind("link", "<Leave>", lambda e: self._chat_text.configure(cursor="arrow"))

    # ------------------------------------------------------------------
    # Input panel (Bottom)
    # ------------------------------------------------------------------
    def _build_input_panel(self, parent):
        input_frame = tk.Frame(parent, bg=_CLR_BG)
        input_frame.pack(fill=tk.X, padx=8, pady=4)

        # Top row: text entry + mic button
        entry_row = tk.Frame(input_frame, bg=_CLR_ENTRY_BG)
        entry_row.pack(fill=tk.X, pady=(0, 4))

        self._input_text = tk.Text(
            entry_row, height=3, wrap=tk.WORD,
            bg=_CLR_ENTRY_BG, fg=_CLR_FG, font=("Segoe UI", 10),
            relief=tk.FLAT, borderwidth=8, insertbackground=_CLR_FG,
        )
        self._input_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._input_text.bind("<Return>", self._on_enter_key)
        self._input_text.bind("<Shift-Return>", lambda e: None)  # allow newline

        self._mic_btn = tk.Button(
            entry_row, text="🎙", font=("Segoe UI", 14),
            bg=_CLR_BTN, fg=_CLR_FG, relief=tk.FLAT,
            width=3, cursor="hand2",
            activebackground=_CLR_BTN_HOVER,
            command=self._on_mic_click,
        )
        self._mic_btn.pack(side=tk.RIGHT, padx=(4, 4), pady=4)

        # Bottom row: buttons
        btn_row = tk.Frame(input_frame, bg=_CLR_BG)
        btn_row.pack(fill=tk.X)

        self._tts_var = tk.BooleanVar(value=self.cfg.get("tts", "enabled", default=False))
        tts_check = tk.Checkbutton(
            btn_row, text="TTS 읽기", variable=self._tts_var,
            bg=_CLR_BG, fg=_CLR_FG, selectcolor=_CLR_ENTRY_BG,
            activebackground=_CLR_BG, activeforeground=_CLR_FG,
            font=("Segoe UI", 9),
        )
        tts_check.pack(side=tk.LEFT)

        btn_send = tk.Button(
            btn_row, text="Send →", font=("Segoe UI", 10, "bold"),
            bg=_CLR_ACCENT, fg=_CLR_BG, relief=tk.FLAT,
            cursor="hand2", padx=16,
            activebackground=_CLR_BTN_HOVER,
            command=self._on_send,
        )
        btn_send.pack(side=tk.RIGHT, padx=(4, 0))
        
        # Monitor Selection Dropdown
        try:
            from src.input.screen_capture import ScreenCapture
            sc = ScreenCapture(self.cfg)
            monitors = sc.list_monitors()
            monitor_opts = ["전체 화면"]
            for m in monitors:
                monitor_opts.append(f"모니터 {m['index']}")
        except Exception:
            monitor_opts = ["전체 화면"]
            
        self._monitor_var = tk.StringVar(value=monitor_opts[0])
        self._monitor_cb = ttk.Combobox(
            btn_row, textvariable=self._monitor_var, values=monitor_opts,
            state="readonly", width=12, font=("Segoe UI", 9)
        )
        self._monitor_cb.pack(side=tk.RIGHT, padx=4)
        
        btn_identify = tk.Button(
            btn_row, text="식별", font=("Segoe UI", 9),
            bg=_CLR_BTN, fg=_CLR_FG, relief=tk.FLAT, cursor="hand2",
            activebackground=_CLR_BTN_HOVER,
            command=self._on_identify_monitors,
        )
        btn_identify.pack(side=tk.RIGHT, padx=4)

        btn_settings = tk.Button(
            btn_row, text="⚙ Settings", font=("Segoe UI", 9),
            bg=_CLR_BTN, fg=_CLR_FG, relief=tk.FLAT, cursor="hand2",
            activebackground=_CLR_BTN_HOVER,
            command=self._on_settings,
        )
        btn_settings.pack(side=tk.RIGHT, padx=4)

        btn_capture = tk.Button(
            btn_row, text="📷 Capture", font=("Segoe UI", 9),
            bg=_CLR_BTN, fg=_CLR_FG, relief=tk.FLAT, cursor="hand2",
            activebackground=_CLR_BTN_HOVER,
            command=self._on_manual_capture,
        )
        btn_capture.pack(side=tk.RIGHT, padx=4)

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------
    def _build_status_bar(self, parent):
        bar = tk.Frame(parent, bg=_CLR_BG_LIGHT, height=28)
        bar.pack(fill=tk.X, side=tk.BOTTOM, padx=0, pady=0)
        bar.pack_propagate(False)

        self._lbl_state = tk.Label(
            bar, text="Idle", font=("Segoe UI", 9),
            bg=_CLR_BG_LIGHT, fg=_CLR_ASST, anchor="w",
        )
        self._lbl_state.pack(side=tk.LEFT, padx=8)

        self._lbl_spinner = tk.Label(
            bar, text="", font=("Consolas", 10),
            bg=_CLR_BG_LIGHT, fg=_CLR_ACCENT, width=2,
        )
        self._lbl_spinner.pack(side=tk.LEFT)

        self._lbl_queue = tk.Label(
            bar, text="Queue 0", font=("Segoe UI", 9),
            bg=_CLR_BG_LIGHT, fg=_CLR_SYSTEM,
        )
        self._lbl_queue.pack(side=tk.LEFT, padx=12)

        self._lbl_model = tk.Label(
            bar, text=f"LLM: {self.cfg.get('llm', 'model_alias', default='—')}",
            font=("Segoe UI", 9), bg=_CLR_BG_LIGHT, fg=_CLR_SYSTEM,
        )
        self._lbl_model.pack(side=tk.RIGHT, padx=8)

    # ==================================================================
    #  Session logic
    # ==================================================================
    def _load_sessions(self):
        sessions = self.db.list_sessions()
        self._session_listbox.delete(0, tk.END)
        self._session_ids.clear()
        for s in sessions:
            self._session_listbox.insert(tk.END, f"  {s['ttl']}")
            self._session_ids.append(s["id"])
        # Auto-select first
        if sessions:
            self._session_listbox.selection_set(0)
            self._current_session_id = sessions[0]["id"]
            self._load_chat_history()

    def _on_new_session(self):
        sid = self.db.create_session()
        self._load_sessions()
        # Select the newest (first in list)
        self._session_listbox.selection_clear(0, tk.END)
        self._session_listbox.selection_set(0)
        self._current_session_id = sid
        self._load_chat_history()

    def _on_session_select(self, event):
        sel = self._session_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self._current_session_id = self._session_ids[idx]
        self._load_chat_history()

    # ==================================================================
    #  Chat display
    # ==================================================================
    def _load_chat_history(self):
        """Reload chat from DB for the current session."""
        self._chat_text.configure(state=tk.NORMAL)
        self._chat_text.delete("1.0", tk.END)

        if not self._current_session_id:
            self._chat_text.configure(state=tk.DISABLED)
            return

        messages = self.db.get_messages(self._current_session_id)
        for msg in messages:
            self._render_message(msg)

        self._chat_text.configure(state=tk.DISABLED)
        self._chat_text.see(tk.END)

    def _render_message(self, msg: dict):
        """Append a single message to the chat text widget."""
        role = msg.get("role", "system")
        content = msg.get("content", "")
        ts = msg.get("create_dt", "")
        latency = msg.get("ltncy_ms")
        model = msg.get("llm_mdl", "")
        cap = msg.get("cap_path", "")

        # Role label
        if role == "user":
            label = "👤 You"
            tag = "user"
        elif role == "assistant":
            label = "🤖 Assistant"
            tag = "assistant"
        elif role == "error":
            label = "⚠ Error"
            tag = "error"
        else:
            label = "ℹ System"
            tag = "system"

        self._chat_text.insert(tk.END, f"{label}  ", tag)
        self._chat_text.insert(tk.END, f"{ts}\n", "meta")
        self._chat_text.insert(tk.END, f"{content}\n", tag)

        # Meta line
        meta_parts = []
        if latency:
            meta_parts.append(f"{latency}ms")
        if model:
            meta_parts.append(model)
        if cap:
            meta_parts.append(f"📎 ")
            self._chat_text.insert(tk.END, " ".join(meta_parts), "meta")
            # Store path in a tag for click handling
            link_tag = f"link_{msg.get('id', 0)}"
            self._chat_text.tag_configure(link_tag, foreground=_CLR_LINK, underline=True)
            self._chat_text.tag_bind(link_tag, "<Button-1>", lambda e, p=cap: self._open_file(p))
            self._chat_text.tag_bind(link_tag, "<Enter>", lambda e: self._chat_text.configure(cursor="hand2"))
            self._chat_text.tag_bind(link_tag, "<Leave>", lambda e: self._chat_text.configure(cursor="arrow"))
            self._chat_text.insert(tk.END, os.path.basename(cap), link_tag)
            self._chat_text.insert(tk.END, "\n", "meta")
        elif meta_parts:
            self._chat_text.insert(tk.END, " ".join(meta_parts) + "\n", "meta")

        self._chat_text.insert(tk.END, "\n")

    def _append_message_to_chat(self, msg: dict):
        """Append a single message and scroll to bottom."""
        self._chat_text.configure(state=tk.NORMAL)
        self._render_message(msg)
        self._chat_text.configure(state=tk.DISABLED)
        self._chat_text.see(tk.END)

    # ==================================================================
    #  Input handlers
    # ==================================================================
    def _on_enter_key(self, event):
        """Send on Enter (Shift+Enter for newline)."""
        self._on_send()
        return "break"

    def _on_send(self):
        """Submit the current text input as a user message."""
        text = self._input_text.get("1.0", tk.END).strip()
        if not text:
            return
        if not self._current_session_id:
            messagebox.showwarning("세션 없음", "먼저 세션을 선택하거나 새 세션을 만들어주세요.")
            return

        self._input_text.delete("1.0", tk.END)

        # Determine input mode
        inp_mode = self._pending_inp_mode if hasattr(self, "_pending_inp_mode") else "text"
        self._pending_inp_mode = "text"  # reset

        # Save user message to DB
        stt_prov = "whisper.cpp" if inp_mode == "voice" else None
        msg_id = self.db.insert_message(
            sess_id=self._current_session_id,
            role="user",
            content=text,
            stt_prov=stt_prov,
            tts_enbl=self._tts_var.get(),
        )

        # Show in chat immediately
        self._append_message_to_chat({
            "id": msg_id, "role": "user", "content": text,
            "create_dt": "", "ltncy_ms": None, "llm_mdl": None, "cap_path": None,
        })

        # Create job
        job_id = self.db.insert_job(
            sess_id=self._current_session_id,
            inp_txt=text,
            llm_prov="LlamaCppOpenAICompat",
            llm_mdl=self.cfg.get("llm", "model_alias", default=""),
            inp_mode=inp_mode,
        )

        # Parse Monitor selection
        mon_val = self._monitor_var.get()
        capture_mode = "full"
        monitor_index = 0
        if mon_val.startswith("모니터"):
            capture_mode = "monitor"
            try:
                monitor_index = int(mon_val.split()[-1]) - 1
            except:
                pass

        # Push to worker queue
        job = Job(
            job_id=job_id,
            session_id=self._current_session_id,
            input_text=text,
            inp_mode=inp_mode,
            tts_enabled=self._tts_var.get(),
            capture_mode=capture_mode,
            monitor_index=monitor_index
        )
        self._job_queue.put(job)
        self._is_running = True
        self._update_status()

        # Auto-update session title from first message
        msgs = self.db.get_messages(self._current_session_id)
        if len(msgs) == 1:
            title = text[:40] + ("…" if len(text) > 40 else "")
            self.db.update_session_title(self._current_session_id, title)
            self._load_sessions()

    def _on_mic_click(self):
        """Toggle microphone recording state."""
        if self._recording:
            # Stop recording
            self._recording = False
            self._mic_btn.configure(bg=_CLR_BTN, text="🎙")
            self._lbl_state.configure(text="STT 변환 중...")

            # In Phase 4 this will call the actual STT provider.
            # For now, show a placeholder message.
            try:
                from src.input.audio_input import WhisperCppSTT
                stt = WhisperCppSTT(self.cfg)
                transcribed = stt.transcribe()
                if transcribed:
                    self._input_text.delete("1.0", tk.END)
                    self._input_text.insert("1.0", transcribed)
                    self._pending_inp_mode = "voice"
                self._lbl_state.configure(text="Idle")
            except Exception as e:
                logger.warning(f"STT failed: {e}")
                self._lbl_state.configure(text="STT 실패")
                self.db.insert_log(level="WARNING", message=f"[stt] {e}")
        else:
            # Start recording
            self._recording = True
            self._mic_btn.configure(bg=_CLR_MIC_REC, text="⏹")
            self._lbl_state.configure(text="🔴 녹음 중...")

    def _on_manual_capture(self):
        """Manually capture the screen."""
        try:
            from src.input.screen_capture import ScreenCapture
            sc = ScreenCapture(self.cfg)
            
            mon_val = self._monitor_var.get()
            capture_mode = "full"
            monitor_index = 0
            if mon_val.startswith("모니터"):
                capture_mode = "monitor"
                try:
                    monitor_index = int(mon_val.split()[-1]) - 1
                except:
                    pass
            
            path = sc.capture(mode=capture_mode, monitor_index=monitor_index)
            logger.info(f"Manual capture: {path}")
            messagebox.showinfo("캡처 완료", f"저장됨:\n{path}")
        except Exception as e:
            logger.error(f"Manual capture failed: {e}")
            messagebox.showerror("캡처 실패", str(e))

    def _on_identify_monitors(self):
        """Show large OSD numbers on each monitor for 2 seconds."""
        try:
            from src.input.screen_capture import ScreenCapture
            sc = ScreenCapture(self.cfg)
            monitors = sc.list_monitors()
            
            for m in monitors:
                top = tk.Toplevel(self)
                top.overrideredirect(True)
                top.attributes("-topmost", True)
                top.attributes("-alpha", 0.8)
                top.config(bg="black")
                
                # Position in center of the monitor
                w, h = 300, 300
                x = m["left"] + (m["width"] - w) // 2
                y = m["top"] + (m["height"] - h) // 2
                top.geometry(f"{w}x{h}+{x}+{y}")
                
                # Text
                lbl = tk.Label(
                    top, text=str(m["index"]), 
                    font=("Segoe UI", 120, "bold"), fg="white", bg="black"
                )
                lbl.pack(expand=True, fill=tk.BOTH)
                
                # Destroy after 2 seconds
                top.after(2000, top.destroy)
                
        except Exception as e:
            logger.error(f"Identify monitors failed: {e}")

    def _on_settings(self):
        """Open the settings dialog."""
        try:
            from src.ui.ui_settings import SettingsDialog
            SettingsDialog(self, self.cfg, self.db)
        except Exception as e:
            logger.error(f"Settings dialog error: {e}")
            messagebox.showerror("설정 오류", str(e))

    def _on_link_click(self, event):
        """Fallback link click handler."""
        pass

    def _open_file(self, path):
        """Open a file using the system default viewer."""
        try:
            os.startfile(path)
        except Exception as e:
            logger.warning(f"Cannot open file {path}: {e}")

    # ==================================================================
    #  Polling & Animation
    # ==================================================================
    def _poll_results(self):
        """Check for completed jobs and update UI."""
        try:
            while True:
                result: WorkerResult = self._result_queue.get_nowait()
                self._handle_result(result)
        except queue.Empty:
            pass

        # Update queue count display
        self._update_status()
        self.after(_POLL_MS, self._poll_results)

    def _handle_result(self, result: WorkerResult):
        """Process a completed job result."""
        job = result.job
        if job.session_id != self._current_session_id:
            return  # Result for a different session tab

        if result.success:
            self._append_message_to_chat({
                "id": 0, "role": "assistant",
                "content": job.result_text,
                "create_dt": "",
                "ltncy_ms": job.latency_ms,
                "llm_mdl": result.llm_model,
                "cap_path": job.capture_path,
            })
        else:
            self._append_message_to_chat({
                "id": 0, "role": "error",
                "content": f"오류 발생: {job.error_msg}",
                "create_dt": "", "ltncy_ms": None,
                "llm_mdl": None, "cap_path": None,
            })

    def _update_status(self):
        """Refresh status bar labels."""
        qc = self._job_queue.qsize()
        if qc > 0 or self._is_running:
            self._lbl_queue.configure(text=f"Queue {qc}")
        else:
            self._lbl_queue.configure(text="Queue 0")
            self._is_running = False

    def _animate_status(self):
        """Cycle spinner and dots while running."""
        if self._is_running or not self._job_queue.empty():
            self._is_running = True
            self._spinner_idx = (self._spinner_idx + 1) % len(_SPINNER)
            self._dots_idx = (self._dots_idx + 1) % len(_DOTS)
            self._lbl_spinner.configure(text=_SPINNER[self._spinner_idx])
            self._lbl_state.configure(
                text=f"추론중입니다{_DOTS[self._dots_idx]}",
                fg=_CLR_ACCENT,
            )
        else:
            self._lbl_spinner.configure(text="")
            if not self._recording:
                self._lbl_state.configure(text="Idle", fg=_CLR_ASST)

        self.after(_ANIM_MS, self._animate_status)

    # ==================================================================
    #  Shutdown
    # ==================================================================
    def _on_close(self):
        """Graceful shutdown."""
        logger.info("Shutting down…")
        self._worker.request_shutdown()
        self.destroy()

`

### File: .\src\ui\ui_settings.py
`python
"""
AMEVA Voice Screen Assistant — Settings Dialog
================================================
Tkinter Toplevel modal that reads/writes settings directly to ``config.json``
through the ``CFG`` singleton.  Changes take effect immediately.
"""

import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

logger = logging.getLogger("ameva.ui_settings")

# Colors (matching main UI theme)
_CLR_BG       = "#1e1e2e"
_CLR_FG       = "#cdd6f4"
_CLR_ENTRY_BG = "#313244"
_CLR_ACCENT   = "#cba6f7"
_CLR_BTN      = "#45475a"
_CLR_BTN_HOVER= "#585b70"


class SettingsDialog(tk.Toplevel):
    """
    Modal settings dialog.

    Parameters
    ----------
    parent : tk.Tk
    cfg : AppConfig
    db : DatabaseManager  (used only for Docker health check logs)
    """

    def __init__(self, parent, cfg, db):
        super().__init__(parent)
        self.cfg = cfg
        self.db = db

        self.title("⚙ Settings")
        self.geometry("560x520")
        self.resizable(False, False)
        self.configure(bg=_CLR_BG)
        self.transient(parent)
        self.grab_set()

        self._vars: dict[str, tk.StringVar | tk.BooleanVar] = {}
        self._build_ui()
        self._load_values()

    # ------------------------------------------------------------------
    #  UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Style tweaks for dark theme
        style = ttk.Style()
        style.configure("TNotebook", background=_CLR_BG)
        style.configure("TNotebook.Tab", background=_CLR_BTN, foreground=_CLR_FG, padding=[10, 4])
        style.map("TNotebook.Tab", background=[("selected", _CLR_ACCENT)])

        # --- LLM tab ---
        tab_llm = tk.Frame(notebook, bg=_CLR_BG)
        notebook.add(tab_llm, text="LLM")
        self._add_entry(tab_llm, "llm.base_url", "Base URL", row=0)
        self._add_entry(tab_llm, "llm.model_alias", "Model Alias", row=1)
        self._add_entry(tab_llm, "llm.temperature", "Temperature", row=2)
        self._add_entry(tab_llm, "llm.max_tokens", "Max Tokens", row=3)
        self._add_entry(tab_llm, "llm.timeout_sec", "Timeout (sec)", row=4)

        # --- Docker tab ---
        tab_docker = tk.Frame(notebook, bg=_CLR_BG)
        notebook.add(tab_docker, text="Docker")
        self._add_entry(tab_docker, "docker.image", "Docker Image", row=0)
        self._add_entry(tab_docker, "docker.container_name", "Container Name", row=1)
        self._add_entry(tab_docker, "docker.port", "Port", row=2)
        
        # Dynamic model selection combo
        self._vars["docker.model_dir"] = tk.StringVar()
        self._vars["docker.model_file"] = tk.StringVar()
        self._vars["docker.mmproj_file"] = tk.StringVar()
        self._add_path_entry(tab_docker, "docker.model_dir", "Model Directory", row=3)
        
        tk.Label(
            tab_docker, text="Model File", font=("Segoe UI", 10),
            bg=_CLR_BG, fg=_CLR_FG, anchor="w",
        ).grid(row=4, column=0, sticky="w", padx=12, pady=6)
        
        self.model_combo = ttk.Combobox(
            tab_docker, textvariable=self._vars["docker.model_file"],
            font=("Segoe UI", 10), state="readonly", width=37
        )
        self.model_combo.grid(row=4, column=1, sticky="ew", padx=12, pady=6)
        
        tk.Label(
            tab_docker, text="Projector (mmproj)", font=("Segoe UI", 10),
            bg=_CLR_BG, fg=_CLR_FG, anchor="w",
        ).grid(row=5, column=0, sticky="w", padx=12, pady=6)
        
        self.mmproj_combo = ttk.Combobox(
            tab_docker, textvariable=self._vars["docker.mmproj_file"],
            font=("Segoe UI", 10), state="readonly", width=37
        )
        self.mmproj_combo.grid(row=5, column=1, sticky="ew", padx=12, pady=6)
        tab_docker.columnconfigure(1, weight=1)
        
        # Bind trace to update model list when directory changes
        self._vars["docker.model_dir"].trace_add("write", lambda *args: self._update_model_list())

        # --- Capture tab ---
        tab_cap = tk.Frame(notebook, bg=_CLR_BG)
        notebook.add(tab_cap, text="캡처")
        self._add_combo(tab_cap, "capture.mode", "캡처 모드", ["full", "monitor"], row=0)
        self._add_entry(tab_cap, "capture.monitor_index", "모니터 인덱스", row=1)
        self._add_path_entry(tab_cap, "capture.root_dir", "저장 경로", row=2)

        # --- STT/TTS tab ---
        tab_voice = tk.Frame(notebook, bg=_CLR_BG)
        notebook.add(tab_voice, text="음성")
        self._add_path_entry(tab_voice, "stt.whisper_executable", "Whisper 실행파일", row=0)
        self._add_path_entry(tab_voice, "stt.whisper_model", "Whisper 모델", row=1)
        self._add_entry(tab_voice, "stt.recording_max_sec", "최대 녹음(초)", row=2)
        self._add_check(tab_voice, "tts.enabled", "TTS 활성화", row=3)

        # --- Save / Cancel ---
        btn_frame = tk.Frame(self, bg=_CLR_BG)
        btn_frame.pack(fill=tk.X, padx=8, pady=(0, 8))

        tk.Button(
            btn_frame, text="저장", font=("Segoe UI", 10, "bold"),
            bg=_CLR_ACCENT, fg=_CLR_BG, relief=tk.FLAT,
            cursor="hand2", padx=20, command=self._on_save,
        ).pack(side=tk.RIGHT, padx=4)

        tk.Button(
            btn_frame, text="취소", font=("Segoe UI", 10),
            bg=_CLR_BTN, fg=_CLR_FG, relief=tk.FLAT,
            cursor="hand2", padx=20, command=self.destroy,
        ).pack(side=tk.RIGHT, padx=4)

    # ------------------------------------------------------------------
    #  Widget helpers
    # ------------------------------------------------------------------
    def _add_entry(self, parent, key, label, row):
        tk.Label(
            parent, text=label, font=("Segoe UI", 10),
            bg=_CLR_BG, fg=_CLR_FG, anchor="w",
        ).grid(row=row, column=0, sticky="w", padx=12, pady=6)

        var = tk.StringVar()
        self._vars[key] = var
        entry = tk.Entry(
            parent, textvariable=var, font=("Segoe UI", 10),
            bg=_CLR_ENTRY_BG, fg=_CLR_FG, insertbackground=_CLR_FG,
            relief=tk.FLAT, width=40,
        )
        entry.grid(row=row, column=1, sticky="ew", padx=12, pady=6)
        parent.columnconfigure(1, weight=1)

    def _add_path_entry(self, parent, key, label, row):
        tk.Label(
            parent, text=label, font=("Segoe UI", 10),
            bg=_CLR_BG, fg=_CLR_FG, anchor="w",
        ).grid(row=row, column=0, sticky="w", padx=12, pady=6)

        var = tk.StringVar()
        self._vars[key] = var

        frame = tk.Frame(parent, bg=_CLR_BG)
        frame.grid(row=row, column=1, sticky="ew", padx=12, pady=6)
        parent.columnconfigure(1, weight=1)

        entry = tk.Entry(
            frame, textvariable=var, font=("Segoe UI", 10),
            bg=_CLR_ENTRY_BG, fg=_CLR_FG, insertbackground=_CLR_FG,
            relief=tk.FLAT,
        )
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(
            frame, text="…", font=("Segoe UI", 9),
            bg=_CLR_BTN, fg=_CLR_FG, relief=tk.FLAT, width=3,
            command=lambda: self._browse_path(var),
        ).pack(side=tk.RIGHT, padx=(4, 0))

    def _add_combo(self, parent, key, label, options, row):
        tk.Label(
            parent, text=label, font=("Segoe UI", 10),
            bg=_CLR_BG, fg=_CLR_FG, anchor="w",
        ).grid(row=row, column=0, sticky="w", padx=12, pady=6)

        var = tk.StringVar()
        self._vars[key] = var
        combo = ttk.Combobox(
            parent, textvariable=var, values=options,
            font=("Segoe UI", 10), state="readonly", width=37,
        )
        combo.grid(row=row, column=1, sticky="ew", padx=12, pady=6)
        parent.columnconfigure(1, weight=1)

    def _add_check(self, parent, key, label, row):
        var = tk.BooleanVar()
        self._vars[key] = var
        tk.Checkbutton(
            parent, text=label, variable=var,
            font=("Segoe UI", 10), bg=_CLR_BG, fg=_CLR_FG,
            selectcolor=_CLR_ENTRY_BG, activebackground=_CLR_BG,
            activeforeground=_CLR_FG,
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=12, pady=6)

    # ------------------------------------------------------------------
    #  Load / Save
    # ------------------------------------------------------------------
    def _load_values(self):
        for key, var in self._vars.items():
            parts = key.split(".")
            val = self.cfg.get(*parts, default="")
            if isinstance(var, tk.BooleanVar):
                var.set(bool(val))
            else:
                # Proactively default model_dir if empty
                if key == "docker.model_dir" and not val:
                    from pathlib import Path
                    if Path("C:/ameva/models").exists():
                        val = "C:/ameva/models"
                var.set(str(val) if val is not None else "")
        
        # Force initial update of model dropdown values
        self._update_model_list()

    def _on_save(self):
        old_dir = self.cfg.get("docker", "model_dir", default="")
        old_file = self.cfg.get("docker", "model_file", default="")
        old_mmproj = self.cfg.get("docker", "mmproj_file", default="")

        for key, var in self._vars.items():
            parts = key.split(".")
            val = var.get()

            # Type coercion for known numeric fields
            if key in ("llm.temperature",):
                try:
                    val = float(val)
                except ValueError:
                    pass
            elif key in ("llm.max_tokens", "llm.timeout_sec", "docker.port",
                         "capture.monitor_index", "stt.recording_max_sec"):
                try:
                    val = int(val)
                except ValueError:
                    pass
            elif isinstance(var, tk.BooleanVar):
                val = var.get()

            self.cfg.set(*parts, val)

        new_dir = self._vars["docker.model_dir"].get()
        new_file = self._vars["docker.model_file"].get()
        new_mmproj = self._vars["docker.mmproj_file"].get()
        if new_mmproj == "None":
            new_mmproj = ""

        # Keep llm.model_alias in sync with chosen GGUF file
        if new_file:
            alias = new_file
            if alias.endswith(".gguf"):
                alias = alias[:-5]
            self.cfg.set("llm", "model_alias", alias)

        # If model or mmproj changes, regenerate docker-compose.yml and restart docker
        if new_dir != old_dir or new_file != old_file or new_mmproj != old_mmproj:
            self._update_docker_compose(new_dir, new_file, new_mmproj)
            self._restart_docker_async()

        logger.info("Settings saved")
        messagebox.showinfo("설정", "설정이 저장되었습니다.", parent=self)
        self.destroy()

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------
    def _update_model_list(self):
        from pathlib import Path
        model_dir = self._vars["docker.model_dir"].get()
        if not model_dir:
            self.model_combo["values"] = []
            self.mmproj_combo["values"] = []
            return

        path = Path(model_dir)
        if path.exists() and path.is_dir():
            try:
                all_files = [p.name for p in path.glob("*")]
                
                # Primary models: end with .gguf and do NOT contain mmproj in name
                gguf_models = [f for f in all_files if f.endswith(".gguf") and "mmproj" not in f.lower()]
                sorted_models = sorted(gguf_models)
                self.model_combo["values"] = sorted_models
                
                current_model = self._vars["docker.model_file"].get()
                if sorted_models:
                    if not current_model or current_model not in sorted_models:
                        self._vars["docker.model_file"].set(sorted_models[0])
                else:
                    self._vars["docker.model_file"].set("")
                
                # Projector (mmproj) files: contain mmproj or have .gguf/.bin
                mmproj_files = [f for f in all_files if "mmproj" in f.lower() or f.endswith(".gguf") or f.endswith(".bin")]
                sorted_mmproj = ["None"] + sorted(list(set(mmproj_files)))
                self.mmproj_combo["values"] = sorted_mmproj
                
                current_mmproj = self._vars["docker.mmproj_file"].get()
                if not current_mmproj or current_mmproj not in sorted_mmproj:
                    self._vars["docker.mmproj_file"].set("None")
                    
            except Exception as e:
                logger.error(f"Error scanning model directory: {e}")
                self.model_combo["values"] = []
                self.mmproj_combo["values"] = []
        else:
            self.model_combo["values"] = []
            self.mmproj_combo["values"] = []

    def _update_docker_compose(self, model_dir: str, model_file: str, mmproj_file: str):
        from pathlib import Path
        compose_path = Path("docker/docker-compose.yml")
        if not compose_path.exists():
            return

        try:
            lines = compose_path.read_text(encoding="utf-8").splitlines()
            new_lines = []
            in_volumes = False

            for line in lines:
                stripped = line.strip()
                if stripped == "volumes:":
                    in_volumes = True
                    new_lines.append(line)
                    continue

                if in_volumes and stripped.startswith("- ") and stripped.endswith(":/models"):
                    indent = line[:line.index("-")]
                    clean_dir = str(Path(model_dir).resolve()).replace("\\", "/")
                    new_lines.append(f"{indent}- {clean_dir}:/models")
                    in_volumes = False
                    continue

                if stripped.startswith("--model "):
                    indent = line[:line.index("--model")]
                    new_lines.append(f"{indent}--model /models/{model_file}")
                    
                    # Automatically append --mmproj line right after --model if specified
                    if mmproj_file:
                        new_lines.append(f"{indent}--mmproj /models/{mmproj_file}")
                    continue

                if stripped.startswith("--mmproj "):
                    # Skip the old mmproj line, we regenerate it right after --model
                    continue

                new_lines.append(line)

            compose_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            logger.info("docker-compose.yml updated with new model and mmproj settings.")
        except Exception as e:
            logger.error(f"Failed to update docker-compose.yml: {e}")

    def _restart_docker_async(self):
        import threading
        import subprocess
        from pathlib import Path

        def run_restart():
            docker_dir = Path("docker")
            logger.info("Restarting docker container with new model settings...")
            try:
                subprocess.run(
                    ["docker", "compose", "down"],
                    cwd=str(docker_dir),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=15
                )
                subprocess.run(
                    ["docker", "compose", "up", "-d"],
                    cwd=str(docker_dir),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=15
                )
                logger.info("Docker container restarted successfully with new model settings.")
            except Exception as e:
                logger.error(f"Failed to restart Docker compose: {e}")

        threading.Thread(target=run_restart, daemon=True).start()

    @staticmethod
    def _browse_path(var: tk.StringVar):
        path = filedialog.askdirectory()
        if path:
            var.set(path)

`

### File: .\tests_harness\fakes.py
`python
"""
AMEVA Test Harness — Fake STT & TTS Providers
===============================================
Drop-in replacements for WhisperCppSTT and WindowsSAPITTS that require
no external binaries or audio hardware.
"""

import logging
import time

logger = logging.getLogger("ameva.fakes")


class FakeWhisperSTT:
    """
    Stub STT that returns a canned response.

    Parameters
    ----------
    response : str
        Fixed text to return for any transcription request.
    delay : float
        Simulated processing time in seconds.
    fail : bool
        If True, raises RuntimeError to test error paths.
    """

    def __init__(self, response: str = "테스트 음성 입력입니다.", delay: float = 0.3, fail: bool = False):
        self.response = response
        self.delay = delay
        self.fail = fail

    def transcribe(self, wav_path: str = None) -> str:
        time.sleep(self.delay)
        if self.fail:
            raise RuntimeError("FakeWhisperSTT: forced failure for testing")
        logger.info(f"FakeWhisperSTT returning: '{self.response}'")
        return self.response


class FakeTTS:
    """
    Stub TTS that logs speak calls without producing audio.
    """

    def __init__(self):
        self.history: list[str] = []

    def speak(self, text: str, **kwargs):
        self.history.append(text)
        logger.info(f"FakeTTS.speak: '{text[:60]}...'")

`

### File: .\tests_harness\manual_test_scenarios.md
`markdown
# AMEVA Test Harness — Manual Test Scenarios

## 시나리오 1: 정상 기본 흐름 (텍스트 채팅)
1. `python run.py` 로 앱 실행
2. 기본 세션이 자동 생성되어 있는지 확인
3. 텍스트 입력창에 "테스트 메시지" 입력 → Send 클릭
4. 상태바에 "추론중입니다..." 애니메이션 표시 확인
5. 응답이 채팅창에 표시되는지 확인
6. DB에 `tb_message` 레코드 2개 (user + assistant) 확인
7. `tb_job` 상태가 `done`인지 확인

## 시나리오 2: 서버가 꺼져 있음
1. llama.cpp 서버가 꺼진 상태에서 앱 실행
2. 메시지 전송
3. 에러 메시지가 채팅창에 빨간색으로 표시되는지 확인
4. `tb_log`에 stage=`llm` 에러 기록 확인
5. 앱이 계속 정상 동작하는지 확인 (freeze 없음)

## 시나리오 3: 추론 중 추가 요청
1. 첫 번째 메시지 전송 (서버 지연 설정: `MOCK_DELAY=5`)
2. 추론 중 두 번째 메시지 입력 → Send
3. Queue 카운트가 증가하는지 확인
4. 첫 번째 완료 후 두 번째가 자동 처리되는지 확인
5. 순서 보장 확인

## 시나리오 4: 마이크 음성 입력 (Mode B)
1. 🎙 마이크 버튼 클릭
2. 버튼이 빨간색(⏹)으로 변하는지 확인
3. 상태바에 "🔴 녹음 중..." 표시 확인
4. 다시 클릭하여 녹음 종료
5. STT 변환 텍스트가 입력창에 삽입되는지 확인
6. 자동 전송이 안 되고 Send 대기 상태인지 확인
7. Send 클릭 후 `tb_job.inp_mode = 'voice'` 확인

## 시나리오 5: TTS OFF/ON 비교
1. TTS 체크박스 OFF → 메시지 전송 → 음성 출력 없음 확인
2. TTS 체크박스 ON → 메시지 전송 → 음성 출력 확인
3. `tb_message.tts_enbl` 값 확인

## 시나리오 6: 세션 복구
1. 세션 A, B 생성 후 각각 메시지 입력
2. 앱 종료
3. 재실행 후 세션 목록에 A, B가 있는지 확인
4. 각 세션 클릭 시 해당 대화 내용이 복원되는지 확인

## 시나리오 7: 설정 변경 및 즉시 적용
1. Settings 버튼 클릭
2. LLM base_url 변경 → 저장
3. 다음 메시지부터 변경된 URL로 요청이 가는지 확인
4. 앱 재실행 후 변경된 설정이 유지되는지 확인

## 시나리오 8: Mock LLM 서버 테스트
```powershell
# 정상 모드
python tests_harness/mock_llm_server.py --port 8080

# 지연 모드 (5초)
$env:MOCK_DELAY=5; python tests_harness/mock_llm_server.py --port 8080

# 에러 모드 (HTTP 500)
$env:MOCK_ERROR=500; python tests_harness/mock_llm_server.py --port 8080

# 잘못된 JSON 모드
$env:MOCK_MALFORMED=1; python tests_harness/mock_llm_server.py --port 8080
```

`

### File: .\tests_harness\mock_llm_server.py
`python
"""
AMEVA Test Harness — Mock LLM Server
======================================
Standalone HTTP server mimicking llama.cpp's OpenAI-compatible API.

Usage::

    python tests_harness/mock_llm_server.py --port 8080

Modes (set via query params or env vars):
  - Normal: echoes the last user message
  - Delay:  ``MOCK_DELAY=5`` adds N seconds latency
  - Error:  ``MOCK_ERROR=500`` returns HTTP 500
  - Malformed: ``MOCK_MALFORMED=1`` returns broken JSON
"""

import json
import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler


MOCK_DELAY = float(os.environ.get("MOCK_DELAY", "0.5"))
MOCK_ERROR = int(os.environ.get("MOCK_ERROR", "0"))
MOCK_MALFORMED = os.environ.get("MOCK_MALFORMED", "0") == "1"
MODEL_ALIAS = os.environ.get("MOCK_MODEL", "mock-gguf-test")


class MockHandler(BaseHTTPRequestHandler):
    """Handles /v1/models and /v1/chat/completions."""

    def do_GET(self):
        if "/v1/models" in self.path:
            self._respond_json(200, {
                "object": "list",
                "data": [{"id": MODEL_ALIAS, "object": "model", "owned_by": "mock"}],
            })
        else:
            self._respond_json(404, {"error": "not found"})

    def do_POST(self):
        if "/v1/chat/completions" not in self.path:
            self._respond_json(404, {"error": "not found"})
            return

        # Simulate delay
        if MOCK_DELAY > 0:
            time.sleep(MOCK_DELAY)

        # Simulate error
        if MOCK_ERROR:
            self._respond_json(MOCK_ERROR, {"error": f"Mock error {MOCK_ERROR}"})
            return

        # Simulate malformed JSON
        if MOCK_MALFORMED:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{broken json here!!!}")
            return

        # Parse request
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")

        try:
            req = json.loads(body)
        except json.JSONDecodeError:
            self._respond_json(400, {"error": "invalid JSON"})
            return

        messages = req.get("messages", [])
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content", "")
                break

        # Generate a friendly mock response if OCR context is injected
        if "[Screen Context from OCR]" in last_user:
            parts = last_user.split("[Screen Context from OCR]")
            actual_question = parts[0].strip()
            ocr_context = parts[1].strip()
            
            lines = ocr_context.split("\n")
            title_count = sum(1 for l in lines if "[TITLE-LIKE]" in l)
            log_count = sum(1 for l in lines if "[LOG-LIKE]" in l)
            btn_count = sum(1 for l in lines if "[BUTTON-LIKE]" in l)
            
            content = (
                f"[가짜 LLM 서버 응답] 질문 확인: '{actual_question}'\n\n"
                f"지금 화면에서 제목형 텍스트 {title_count}개, 에러/로그 {log_count}개, 버튼형 텍스트 {btn_count}개가 "
                f"Tesseract OCR을 통해 성공적으로 감지되었습니다!\n\n"
                f"실제 도커(Docker) LLM 서버가 연결되면 이 데이터를 분석하여 진짜 답변을 드립니다."
            )
        else:
            content = f"[Mock LLM Response] 입력: {last_user}"

        # Echo response
        response = {
            "id": "mock-chatcmpl-001",
            "object": "chat.completion",
            "model": MODEL_ALIAS,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }

        self._respond_json(200, response)

    def _respond_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        print(f"[MockLLM] {args[0]}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Mock LLM Server")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    server = HTTPServer(("0.0.0.0", args.port), MockHandler)
    print(f"Mock LLM server running on http://0.0.0.0:{args.port}")
    print(f"  MOCK_DELAY={MOCK_DELAY}s  MOCK_ERROR={MOCK_ERROR}  MOCK_MALFORMED={MOCK_MALFORMED}")
    print("  Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down mock server")
        server.server_close()


if __name__ == "__main__":
    main()

`

### File: .\tests_harness\sample_db_builder.py
`python
"""
AMEVA Test Harness — Sample Database Builder
==============================================
Seeds the SQLite database with demo sessions, messages, jobs, and logs
for UI testing and demonstration purposes.

Usage::

    python tests_harness/sample_db_builder.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import CFG
from src.database import DatabaseManager


def build_sample_data():
    db_path = CFG.resolve_path(CFG.get("db", "path", default="db/ameva_assistant.db"))
    db = DatabaseManager(db_path)

    print(f"Building sample data in: {db_path}")

    # --- Session 1: Error debugging ---
    s1 = db.create_session("Python 에러 디버깅")
    db.insert_message(s1, "user", "이 에러 뭔지 알려줘: TypeError: 'NoneType' object is not iterable")
    db.insert_message(
        s1, "assistant",
        "이 에러는 None 값을 반복(iterate)하려고 할 때 발생합니다.\n\n"
        "예를 들어:\n```python\nfor item in some_function():\n    print(item)\n```\n"
        "여기서 `some_function()`이 `None`을 반환하면 이 에러가 발생합니다.\n\n"
        "해결 방법:\n1. 반환값이 None인지 먼저 확인\n2. 기본값을 빈 리스트로 설정",
        llm_prov="LlamaCppOpenAICompat", llm_mdl="local-gguf", ltncy_ms=1250,
    )
    db.insert_message(s1, "user", "그러면 None 체크는 어떻게 해?")
    db.insert_message(
        s1, "assistant",
        "```python\nresult = some_function()\nif result is not None:\n    for item in result:\n        print(item)\n```\n\n"
        "또는 기본값을 사용할 수 있습니다:\n```python\nfor item in (some_function() or []):\n    print(item)\n```",
        llm_prov="LlamaCppOpenAICompat", llm_mdl="local-gguf", ltncy_ms=980,
    )
    print(f"  Session 1: {s1} (4 messages)")

    # --- Session 2: 화면 분석 ---
    s2 = db.create_session("화면 캡처 분석 테스트")
    db.insert_message(s2, "user", "지금 화면에 뭐가 보이는지 설명해줘", cap_path="data/captures/sample/cap_test.png")
    db.insert_message(
        s2, "assistant",
        "현재 화면에는 코드 에디터(VS Code)가 열려 있습니다.\n"
        "Python 파일이 편집 중이며, 터미널 패널에 테스트 출력이 보입니다.",
        llm_prov="LlamaCppOpenAICompat", llm_mdl="local-gguf",
        ltncy_ms=2100, cap_path="data/captures/sample/cap_test.png",
    )
    print(f"  Session 2: {s2} (2 messages)")

    # --- Session 3: 음성 입력 테스트 ---
    s3 = db.create_session("음성 입력 테스트")
    db.insert_message(s3, "user", "안녕하세요 음성 테스트입니다", stt_prov="whisper.cpp")
    db.insert_message(
        s3, "assistant",
        "안녕하세요! 음성 입력이 잘 인식되었네요. 무엇을 도와드릴까요?",
        llm_prov="LlamaCppOpenAICompat", llm_mdl="local-gguf", ltncy_ms=750,
    )
    print(f"  Session 3: {s3} (2 messages)")

    # --- Sample jobs ---
    j1 = db.insert_job(s1, "이 에러 뭔지 알려줘", inp_mode="text")
    db.update_job_state(j1, "done")
    j2 = db.insert_job(s3, "안녕하세요 음성 테스트입니다", inp_mode="voice")
    db.update_job_state(j2, "done")

    # --- Sample logs ---
    db.insert_log(level="INFO", message="Application started")
    db.insert_log(level="WARNING", message="[stt] whisper.cpp not found — using fallback")
    db.insert_log(level="ERROR", message="[llm] Connection refused: http://127.0.0.1:8080/v1/models",
                  tb="Traceback (most recent call last):\n  ...\nConnectionError: Connection refused")

    print("\nSample data built successfully!")
    print(f"  Sessions: {len(db.list_sessions())}")


if __name__ == "__main__":
    build_sample_data()

`

### File: .\tests_harness\test_router.py
`python
import pytest
from src.orchestration.router import FallbackRouter

def test_fast_track_routing():
    # Affordance queries should fast-track
    assert FallbackRouter.should_fast_track_to_vlm("저 버튼 어디 있어?") == True
    assert FallbackRouter.should_fast_track_to_vlm("오류 로그 분석해줘") == False
    assert FallbackRouter.should_fast_track_to_vlm("무슨 모양인가요?") == True

def test_ocr_fallback_routing():
    # Less than 5 blocks
    assert FallbackRouter.should_fallback_based_on_ocr([
        {"text": "A", "confidence": 0.9}, {"text": "B", "confidence": 0.9}
    ]) == True
    
    # Low confidence
    blocks = [{"text": "Hello World This Is Text", "confidence": 0.4} for _ in range(6)]
    assert FallbackRouter.should_fallback_based_on_ocr(blocks) == True
    
    # Low character count
    blocks2 = [{"text": "A", "confidence": 0.9} for _ in range(6)]
    assert FallbackRouter.should_fallback_based_on_ocr(blocks2) == True
    
    # Good OCR
    blocks3 = [{"text": "Hello World This Is Good Text", "confidence": 0.9} for _ in range(6)]
    assert FallbackRouter.should_fallback_based_on_ocr(blocks3) == False

def test_llm_failure_routing():
    assert FallbackRouter.should_fallback_based_on_llm_failure("어쩌고 저쩌고 정확히 판단하기 어렵다.") == True
    assert FallbackRouter.should_fallback_based_on_llm_failure("이 화면은 편집기입니다.") == False

`

### File: .\tests_harness\test_scene_graph.py
`python
"""
Tests for Phase 2: Scene Graph Builder (Layout Segmentation & Context Compression)
"""

import json
from src.semantic.scene_graph_builder import SceneGraphBuilder

class DummyCfg:
    def get(self, *args, **kwargs):
        return kwargs.get("default", None)

def test_scene_graph_relevance():
    builder = SceneGraphBuilder(DummyCfg())
    
    mock_ocr = {
        "resolution": {"width": 1920, "height": 1080},
        "blocks": [
            # Toolbar area (y < 162)
            {"text": "File", "bbox": [10, 10, 50, 40], "confidence": 0.9},
            {"text": "Edit", "bbox": [60, 10, 100, 40], "confidence": 0.9},
            {"text": "View", "bbox": [110, 10, 150, 40], "confidence": 0.9},
            {"text": "Draw", "bbox": [160, 10, 200, 40], "confidence": 0.9},
            {"text": "Help", "bbox": [210, 10, 250, 40], "confidence": 0.9},
            {"text": "Tools", "bbox": [260, 10, 300, 40], "confidence": 0.9},
            # Sidebar area (x < 480)
            {"text": "Project Explorer", "bbox": [10, 200, 200, 230], "confidence": 0.9},
            {"text": "main.py", "bbox": [20, 240, 100, 260], "confidence": 0.9},
            {"text": "utils.py", "bbox": [20, 270, 100, 290], "confidence": 0.9},
            {"text": "config.py", "bbox": [20, 300, 100, 320], "confidence": 0.9},
            {"text": "app.py", "bbox": [20, 330, 100, 350], "confidence": 0.9},
            {"text": "test.py", "bbox": [20, 360, 100, 380], "confidence": 0.9},
            # Body area (center)
            {"text": "def draw_circle():", "bbox": [500, 500, 700, 530], "confidence": 0.9},
            {"text": "    pass", "bbox": [500, 540, 600, 570], "confidence": 0.9},
            # Status bar area (y > 1026)
            {"text": "Ln 10, Col 5", "bbox": [1500, 1050, 1600, 1070], "confidence": 0.9},
            {"text": "UTF-8", "bbox": [1620, 1050, 1680, 1070], "confidence": 0.9},
            {"text": "Python 3.12", "bbox": [1700, 1050, 1800, 1070], "confidence": 0.9},
            {"text": "Plain Text", "bbox": [1820, 1050, 1900, 1070], "confidence": 0.9},
        ]
    }
    
    # 1. Ask about drawing (should prioritize toolbar and body)
    graph, summary = builder.build(mock_ocr, "그림 그리려면 어떻게 해?")
    
    # Toolbar has 6 items, drawing question should keep them visible
    assert "--- [REGION: TOOLBAR] ---" in summary
    assert "[TEXT] Draw" in summary
    
    # Sidebar has 6 items, drawing question should hide them
    assert "--- [REGION: SIDEBAR] (6 items hidden) ---" in summary
    assert "main.py" not in summary
    
    # Status bar has 4 items, drawing question should hide them
    assert "--- [REGION: STATUS_BAR] (4 items hidden) ---" in summary
    assert "Plain Text" not in summary
    
    # 2. Ask about status/memory (should prioritize status bar)
    graph2, summary2 = builder.build(mock_ocr, "현재 메모리 상태가 어때?")
    
    # Toolbar has 6 items, status question should hide them
    assert "--- [REGION: TOOLBAR] (6 items hidden) ---" in summary2
    
    # Status bar has 4 items, status question should keep them visible
    assert "--- [REGION: STATUS_BAR] ---" in summary2
    assert "[TEXT] Plain Text" in summary2

if __name__ == "__main__":
    test_scene_graph_relevance()
    print("All tests passed!")

`

### File: .\tests_harness\test_vlm_client.py
`python
import pytest
from src.reasoning.vlm_client import LocalMockMultimodalAdapter, LocalLlamaCppMultimodalAdapter

def test_mock_adapter():
    adapter = LocalMockMultimodalAdapter()
    result = adapter.generate("dummy.png", "어떤 모양이야?")
    assert "local_vlm_unavailable" in result
    assert "어떤 모양이야?" in result

def test_llama_cpp_adapter_no_connection():
    adapter = LocalLlamaCppMultimodalAdapter(endpoint_url="http://localhost:9999/v1/invalid")
    
    # Needs a real file to encode
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        tf.write(b"fake_image_bytes")
        tf_name = tf.name
        
    import os
    try:
        with pytest.raises(ConnectionError):
            adapter.generate(tf_name, "test prompt")
    finally:
        os.unlink(tf_name)

`

### File: .\tests_harness\__init__.py
`python
# tests_harness package

`

