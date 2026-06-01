"""
AMEVA Voice Screen Assistant — OCR Interface
============================================
Defines the standard interface for OCR providers.
"""

from typing import Any, Protocol


class OCRProvider(Protocol):
    """Protocol for OCR engines."""

    def extract_text_blocks(self, image_path: str) -> dict[str, Any]:
        """
        Extract text from an image.

        Returns a dictionary matching the schema:
        {
            "engine": str,
            "image_path": str,
            "blocks": [
                {
                    "text": str,
                    "bbox": [x1, y1, x2, y2],
                    "confidence": float
                },
                ...
            ]
        }
        """
        ...
