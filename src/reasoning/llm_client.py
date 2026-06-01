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

        import time
        logger.info(f"[TextLLM] Sending generation request to {url} (Model: {self.model_alias})")
        logger.debug(f"[TextLLM] Payload messages: {json.dumps(messages, ensure_ascii=False)[:1500]}...")
        t0 = time.perf_counter()

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                latency_ms = int((time.perf_counter() - t0) * 1000)
                logger.info(f"[TextLLM] Received response in {latency_ms}ms")
                logger.debug(f"[TextLLM] Raw response body: {body[:1000]}...")
        except urllib.error.URLError as e:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            logger.error(f"[TextLLM] Connection failed after {latency_ms}ms: {e}")
            raise ConnectionError(f"LLM server unreachable: {e}") from e
        except TimeoutError:
            logger.error(f"[TextLLM] Request timed out ({self.timeout}s)")
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
