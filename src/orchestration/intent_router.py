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
    """Uses a local Qwen LLM on port 8782 to classify intent."""
    
    def __init__(self, endpoint_url="http://127.0.0.1:8782/v1/chat/completions"):
        self.endpoint_url = endpoint_url
        self.timeout = 30
        
        # Simplified system prompt for Qwen 0.5B fallback
        self.system_prompt = (
            "당신은 사용자의 질문을 'OCR'과 'VLM' 중 하나로 분류하는 라우팅 에이전트입니다.\n\n"
            "사용자의 질문이 화면 속 텍스트(글자)를 읽거나, 번역하거나, 요약해달라는 것이라면 'OCR'이라고 답하세요.\n"
            "화면이 어떤 화면인지 묻거나, 색상, 레이아웃, 버튼 위치 등 시각적 요소를 묻는 것이라면 'VLM'이라고 답하세요.\n\n"
            "대답은 오직 'OCR' 또는 'VLM' 중 하나로만 하세요. 다른 단어는 절대 추가하지 마세요."
        )

    def route(self, user_input: str) -> Tuple[str, str, str]:
        """
        Returns (decision, reason, translated_prompt).
        Decision is either "VLM" or "OCR".
        """
        import time
        import re

        user_input_clean = user_input.strip().lower()
        
        # OCR Keywords (high precision text reading indicators)
        ocr_keywords = [
            r"읽어", r"써있", r"써 있", r"적혀", r"뭐라", r"글자", r"텍스트", 
            r"요약", r"번역", r"영어", r"한글", r"내용", r"뜻"
        ]
        
        # VLM Keywords (visual elements, screen identity, layout indicators)
        vlm_keywords = [
            r"화면", r"디자인", r"레이아웃", r"버튼", r"아이콘", r"색", 
            r"그림", r"이미지", r"정체", r"뭐야", r"어디", r"위치", r"모양"
        ]
        
        # 1. Fast-track keyword match for OCR
        for kw in ocr_keywords:
            if re.search(kw, user_input_clean):
                logger.info(f"[IntentRouter] Fast-track OCR match on keyword: '{kw}'")
                return "OCR", f"키워드 분석 ('{kw}')에 의해 OCR로 판단됨", user_input
                
        # 2. Fast-track keyword match for VLM
        for kw in vlm_keywords:
            if re.search(kw, user_input_clean):
                logger.info(f"[IntentRouter] Fast-track VLM match on keyword: '{kw}'")
                return "VLM", f"키워드 분석 ('{kw}')에 의해 VLM으로 판단됨", user_input

        # 3. Model Fallback if ambiguous
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input}
        ]
        payload = {
            "model": "qwen2.5-0.5b-q4_k_m",
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 10
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
                
                decision = "VLM"
                if "ocr" in content.lower():
                    decision = "OCR"
                elif "vlm" in content.lower():
                    decision = "VLM"
                
                cause = f"Qwen Router ({latency_ms}ms): {content}"
                logger.info(f"[IntentRouter] Parsed Decision: {decision} | Cause: {cause}")
                return decision, cause, user_input
                
        except Exception as e:
            logger.warning(f"[IntentRouter] Routing model call failed: {e}. Defaulting to VLM.")
            return "VLM", f"Router Model Error/Timeout: {str(e)}", user_input
