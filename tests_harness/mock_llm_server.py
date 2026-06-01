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
        has_image = False
        for m in reversed(messages):
            if m.get("role") == "user":
                content_val = m.get("content", "")
                if isinstance(content_val, list):
                    text_parts = []
                    for item in content_val:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
                            elif item.get("type") == "image_url":
                                has_image = True
                    last_user = " ".join(text_parts)
                else:
                    last_user = str(content_val)
                break

        # Generate a friendly mock response if OCR context is injected
        if has_image:
            content = (
                f"[가짜 VLM 서버 응답] 질문 확인: '{last_user}'\n\n"
                f"이미지 데이터(Base64)가 감지되었습니다!\n"
                f"실제 도커(Docker) VLM 서버가 연결되면 Moondream2 모델을 사용해 화면의 시각 요소를 직접 분석하여 진짜 답변을 드립니다."
            )
        elif "[Screen Context from OCR]" in last_user:
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
