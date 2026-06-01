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
