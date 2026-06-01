import pytest
from src.perception.ocr.postprocessor import OCRPostProcessor

def test_postprocessor_vertical_overlap_merging():
    # Simulate the scrambled coordinates from the user's screenshot
    # "What is the purpose of this screen?"
    # 'What' is at y=39, height=9, but 'is', 'the', 'of', 'this' are at y=28, height=30
    raw_blocks = [
        {"text": "is", "bbox": [117, 28, 128, 58], "confidence": 0.86},
        {"text": "the", "bbox": [132, 28, 145, 58], "confidence": 0.86},
        {"text": "of", "bbox": [195, 28, 205, 58], "confidence": 0.67},
        {"text": "this", "bbox": [210, 28, 228, 58], "confidence": 0.88},
        {"text": "What", "bbox": [88, 39, 147, 48], "confidence": 0.95},
        {"text": "purpose", "bbox": [149, 39, 227, 51], "confidence": 0.59},
        {"text": "screen?", "bbox": [230, 39, 269, 48], "confidence": 0.68},
    ]

    postprocessor = OCRPostProcessor(min_confidence=0.3)
    merged = postprocessor.process(raw_blocks)

    # Should merge everything into one single line block in correct reading order
    assert len(merged) == 1
    assert merged[0]["text"] == "What is the purpose of this screen?"
