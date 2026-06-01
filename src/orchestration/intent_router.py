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
        payload = {
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"User Input: {user_input}"}
            ],
            "temperature": 0.0,
            "max_tokens": 128,
            # Force JSON format if supported by llama.cpp
            "response_format": {"type": "json_object"}
        }

        try:
            req = urllib.request.Request(
                self.endpoint_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                result = json.loads(body)
                content = result["choices"][0]["message"]["content"].strip()
                
                # Cleanup potential markdown wrap
                if content.startswith("```json"):
                    content = content[7:-3].strip()
                elif content.startswith("```"):
                    content = content[3:-3].strip()
                    
                parsed = json.loads(content)
                route_decision = parsed.get("route", "OCR").upper()
                if route_decision not in ["VLM", "OCR"]:
                    route_decision = "OCR"
                cause = parsed.get("cause", "No reason provided")
                translated = parsed.get("translated_prompt", user_input)
                
                logger.info(f"[IntentRouter] Decision: {route_decision} | Reason: {cause} | Translated: {translated}")
                return route_decision, cause, translated
                
        except json.JSONDecodeError as e:
            logger.warning(f"[IntentRouter] JSON Parse Error: {e}. Raw content: {content}")
            return "OCR", "Router JSON Error", user_input
        except Exception as e:
            logger.warning(f"[IntentRouter] Routing failed or timed out: {e}. Falling back to OCR.")
            return "OCR", f"Router Error: {str(e)}", user_input
