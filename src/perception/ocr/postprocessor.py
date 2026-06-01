"""
AMEVA Voice Screen Assistant — OCR Post-processor
=================================================
Cleans, filters, and merges raw OCR bounding boxes to reduce noise and
improve semantic grouping (e.g. combining words on the same line).
"""

import logging
from typing import Any

logger = logging.getLogger("ameva.perception.ocr.postprocessor")


class OCRPostProcessor:
    """Post-processes raw OCR bounding boxes."""

    def __init__(self, min_confidence: float = 0.3, max_x_gap_multiplier: float = 1.5, max_y_diff_multiplier: float = 0.5):
        """
        Args:
            min_confidence: Ignore blocks with confidence below this threshold (0.0 to 1.0)
            max_x_gap_multiplier: Max horizontal gap between boxes to merge, as a multiple of box height.
            max_y_diff_multiplier: Max vertical difference between tops to consider them on the same line.
        """
        self.min_confidence = min_confidence
        self.max_x_gap_multiplier = max_x_gap_multiplier
        self.max_y_diff_multiplier = max_y_diff_multiplier

    def process(self, raw_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Filters and merges raw blocks.
        Raw block schema: {"text": str, "bbox": [x1, y1, x2, y2], "confidence": float}
        """
        # 1. Filter out noise and empty text
        import re
        valid_blocks = []
        for b in raw_blocks:
            text = b.get("text", "").strip()
            conf = b.get("confidence", 0.0)
            
            # Short noise token removal (1 char or special character junk)
            if len(text) <= 1 and not text.isalnum():
                continue
            if re.match(r"^[^a-zA-Z0-9가-힣]+$", text): # Only symbols
                continue
                
            if text and conf >= self.min_confidence:
                valid_blocks.append(b)

        if not valid_blocks:
            return []

        # 2. Sort by Y (top) then X (left)
        valid_blocks.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))

        # 3. Merge adjacent blocks on the same line
        merged_blocks = []
        current_block = valid_blocks[0].copy()

        for next_block in valid_blocks[1:]:
            c_x1, c_y1, c_x2, c_y2 = current_block["bbox"]
            n_x1, n_y1, n_x2, n_y2 = next_block["bbox"]

            c_height = c_y2 - c_y1
            n_height = n_y2 - n_y1
            avg_height = (c_height + n_height) / 2.0

            y_diff = abs(c_y1 - n_y1)
            x_gap = n_x1 - c_x2

            # Check if they are on the same line and close enough horizontally
            same_line = y_diff < (avg_height * self.max_y_diff_multiplier)
            # x_gap can be slightly negative if boxes overlap
            close_horizontally = x_gap < (avg_height * self.max_x_gap_multiplier)

            if same_line and close_horizontally:
                # Merge next_block into current_block
                current_block["text"] += " " + next_block["text"]
                current_block["bbox"] = [
                    min(c_x1, n_x1),
                    min(c_y1, n_y1),
                    max(c_x2, n_x2),
                    max(c_y2, n_y2)
                ]
                # Average confidence (weighted by text length could be better, but simple average is fine)
                current_block["confidence"] = round((current_block["confidence"] + next_block["confidence"]) / 2.0, 3)
            else:
                # Push current and start new
                merged_blocks.append(current_block)
                current_block = next_block.copy()

        # Push the last block
        if current_block:
            merged_blocks.append(current_block)

        return merged_blocks
