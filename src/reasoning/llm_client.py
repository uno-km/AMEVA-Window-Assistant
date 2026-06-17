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
        Supports recursive Tool Calling loop via MCP Client.
        """
        self.base_url = self.cfg.get("llm", "base_url", default=self.base_url)
        self.model_alias = self.cfg.get("llm", "model_alias", default=self.model_alias)
        url = f"{self.base_url}/chat/completions"

        import time
        import os
        from src.reasoning.sync_mcp_client import SyncMCPClient

        # [Phase 1] 하드코딩된 MCP 서버 (AMEVA-MCP-Toolkit-Utils) 로드
        mcp_client = None
        mcp_tools = []
        try:
            mcp_script_path = r"C:\ameva\AMEVA-MCP-Toolkit-Utils\src\server.py"
            if os.path.exists(mcp_script_path):
                mcp_client = SyncMCPClient(mcp_script_path)
                mcp_tools = mcp_client.get_tools()
                logger.info(f"[TextLLM] Loaded {len(mcp_tools)} tools from MCP Server")
        except Exception as e:
            logger.warning(f"[TextLLM] Failed to load MCP tools: {e}")

        # Tool Calling Loop (최대 3번)
        MAX_LOOPS = 3
        loop_count = 0

        while loop_count < MAX_LOOPS:
            loop_count += 1
            payload = {
                "model": self.model_alias,
                "messages": messages,
                "temperature": kwargs.get("temperature", self.temperature),
                "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                "frequency_penalty": 1.15,
                "presence_penalty": 0.1,
                "stream": False,
            }

            if mcp_tools:
                payload["tools"] = mcp_tools
                payload["tool_choice"] = "auto"

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}, method="POST"
            )

            logger.info(f"[TextLLM] Loop {loop_count} - Sending request to {url}")
            t0 = time.perf_counter()

            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = resp.read().decode("utf-8")
                    latency_ms = int((time.perf_counter() - t0) * 1000)
                    logger.info(f"[TextLLM] Received response in {latency_ms}ms")
            except Exception as e:
                raise ConnectionError(f"LLM server unreachable or error: {e}") from e

            try:
                result = json.loads(body)
            except json.JSONDecodeError as e:
                raise ValueError(f"LLM returned invalid JSON: {body[:200]}") from e

            try:
                choice = result["choices"][0]["message"]
            except (KeyError, IndexError) as e:
                raise ValueError(f"Unexpected LLM response structure: {result}") from e

            # 툴 호출(tool_calls) 확인
            if "tool_calls" in choice and choice["tool_calls"]:
                tool_calls = choice["tool_calls"]
                logger.info(f"[TextLLM] LLM wants to call tools: {[tc['function']['name'] for tc in tool_calls]}")
                
                # Assistant의 tool_call 메시지를 대화 기록에 추가
                messages.append(choice)

                # 각 툴 실행
                for tc in tool_calls:
                    func_name = tc["function"]["name"]
                    call_id = tc.get("id", "call_1")
                    try:
                        args = json.loads(tc["function"]["arguments"])
                        logger.info(f"[TextLLM] Executing MCP Tool: {func_name} with args {args}")
                        tool_result = mcp_client.execute_tool(func_name, args)
                    except Exception as e:
                        tool_result = f"Error executing tool: {e}"

                    # 결과를 tool 역할 메시지로 추가
                    messages.append({
                        "role": "tool",
                        "name": func_name,
                        "tool_call_id": call_id,
                        "content": str(tool_result)
                    })
                
                # 툴 실행 결과를 달았으므로 다시 LLM에게 전송하여 최종 답변 요구
                continue

            else:
                # 툴 호출이 없으면 최종 답변 반환
                content = choice.get("content", "")
                if loop_count > 1:
                    content = f"🛠️ **[도구 사용 완료]**\n\n{content}"
                return content

        return "Error: Exceeded maximum tool calling loops."


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
