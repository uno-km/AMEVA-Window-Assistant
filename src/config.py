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
    "vlm": {
        "provider": "llama_cpp",
        "endpoint": "http://127.0.0.1:9083/v1/chat/completions",
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
