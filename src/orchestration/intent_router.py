"""
AMEVA Voice Screen Assistant — Qwen Intent Router
=================================================
Ultra-lightweight local routing using Qwen on port 8082.
It forces a strict JSON output deciding between "VLM" and "OCR",
along with the one-line reasoning.
"""

import json
import logging
import urllib.request
import urllib.error
from typing import Tuple

logger = logging.getLogger("ameva.router.intent")

class IntentRouter:
    """Uses a local Qwen LLM on port 8082 to classify intent."""
    
    def __init__(self, endpoint_url="http://127.0.0.1:8082/v1/chat/completions"):
        self.endpoint_url = endpoint_url
        self.timeout = 10
        
        # We craft a highly constrained system prompt for Qwen.
        self.system_prompt = (
            "You are an ultra-fast, intelligent routing agent for AMEVA (AI Assistant).\n"
            "Your ONLY task is to decide whether a user's prompt requires visual scene/image understanding (VLM) "
            "or text/content understanding (OCR).\n"
            "Additionally, you MUST translate the user's prompt into concise English, as the VLM is an English-centric model.\n\n"
            "## Rules for Classification:\n"
            "1. Route to 'VLM' if the user asks 'what screen is this?', 'what is this?', 'describe the layout', 'where is the button?', 'what color', or asks to identify visual elements.\n"
            "2. Route to 'OCR' if the user asks to summarize text, translate, read the content, or asks 'what does it say?'.\n"
            "3. **When in doubt or if it's a general question about the screen state, strongly prefer 'VLM'.**\n\n"
            "## Output Format (Strict JSON ONLY):\n"
            "You MUST output exactly valid JSON and nothing else. Do not use markdown wrappers.\n"
            "Schema: {\"route\": \"VLM\" or \"OCR\", \"cause\": \"one line reason in Korean\", \"translated_prompt\": \"English translation of the user's input\"}\n\n"
            "Example 1:\n"
            '{"route": "VLM", "cause": "화면 전체의 정체(무슨 화면인지)를 묻는 질문이므로 시각적 이해가 필요함", "translated_prompt": "What screen is this?"}\n\n'
            "Example 2:\n"
            '{"route": "OCR", "cause": "화면에 적힌 내용을 요약해 달라고 했으므로 텍스트 파악이 중요함", "translated_prompt": "Please summarize the text on this screen."}'
        )

    def route(self, user_input: str) -> Tuple[str, str, str]:
        """
        Returns (decision, reason, translated_prompt).
        Decision is either "VLM" or "OCR".
        """
        import time
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"User Prompt: {user_input}"}
        ]
        payload = {
            "model": "qwen2.5-1.5b-instruct",
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 150
        }
        
        logger.info(f"[IntentRouter] Requesting route decision from {self.endpoint_url}")
        logger.debug(f"[IntentRouter] Payload sent: {json.dumps(payload, ensure_ascii=False)}")
        t0 = time.perf_counter()
        
        try:
            req = urllib.request.Request(
                self.endpoint_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                latency_ms = int((time.perf_counter() - t0) * 1000)
                resp_text = response.read().decode("utf-8")
                
                logger.info(f"[IntentRouter] Received response in {latency_ms}ms")
                logger.debug(f"[IntentRouter] Raw response: {resp_text}")
                
                data = json.loads(resp_text)
                content = data["choices"][0]["message"]["content"].strip()
                
                # Remove markdown code blocks if any
                if content.startswith("```"):
                    lines = content.split('\n')
                    if len(lines) >= 3:
                        content = '\n'.join(lines[1:-1])
                        
                parsed = json.loads(content)
                decision = parsed.get("route", "VLM")
                cause = parsed.get("cause", "")
                translated = parsed.get("translated_prompt", "")
                
                logger.info(f"[IntentRouter] Parsed Decision: {decision} | Cause: {cause}")
                return decision, cause, translated
                
        except json.JSONDecodeError as e:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            logger.error(f"[IntentRouter] JSON decode failed after {latency_ms}ms. Content: {content if 'content' in locals() else 'N/A'}")
            return "VLM", f"Parse error: {e}", ""
        except Exception as e:
            logger.warning(f"[IntentRouter] Routing failed or timed out: {e}. Falling back to OCR.")
            return "OCR", f"Router Error: {str(e)}", user_input
