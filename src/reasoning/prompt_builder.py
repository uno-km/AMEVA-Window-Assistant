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
            "6. 확실한 경우는 근거를 제시, 애매하면 '~처럼 보인다'로 추정, 판단 불가면 '판단 어렵다'고 명시하라.\n"
            "7. 사용자가 한국어로 질문하면 번역 요청 여부와 상관없이 반드시 한국어로 친절하게 답변하라."
        )
        system_prompt = f"{base_prompt}\n\n{strict_rules}"

        messages = [{"role": "system", "content": system_prompt}]

        # Load recent conversation history from this session
        import re
        history = self.db.get_messages(job_session_id)
        for msg in history[-20:]:  # last 20 messages for context window
            content = msg["content"]
            if msg["role"] == "assistant":
                # Remove <details><summary>...</summary>...</details> to prevent the model from repeating details blocks.
                content = re.sub(r'<details\b[^>]*>.*?</details>\s*', '', content, flags=re.DOTALL).strip()
            messages.append({"role": msg["role"], "content": content})

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
