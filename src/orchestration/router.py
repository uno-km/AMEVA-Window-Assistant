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
        NOTE: Disabled as a standalone trigger until the classifier is fully implemented.
        It serves as a supplementary context rather than a direct fallback condition.
        """
        stype = scene_graph.get("screen_type", "unknown_application")
        if stype == "unknown_application":
            logger.info("[Router] Scene graph classification is 'unknown_application'. Logging for supplementary context (SG-only fallback disabled).")
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
