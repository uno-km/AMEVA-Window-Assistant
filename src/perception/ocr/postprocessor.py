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

        # 2. Group into lines based on vertical overlap.
        # First sort by top Y coordinate to process top-to-bottom.
        valid_blocks.sort(key=lambda b: b["bbox"][1])
        
        lines = [] # list of lists of blocks
        
        for block in valid_blocks:
            y1_b, y2_b = block["bbox"][1], block["bbox"][3]
            height_b = y2_b - y1_b
            if height_b <= 0:
                continue
                
            placed = False
            for line in lines:
                # Calculate vertical boundaries of the line
                l_y1 = min(member["bbox"][1] for member in line)
                l_y2 = max(member["bbox"][3] for member in line)
                l_height = l_y2 - l_y1
                
                overlap_y1 = max(y1_b, l_y1)
                overlap_y2 = min(y2_b, l_y2)
                overlap_height = overlap_y2 - overlap_y1
                
                if overlap_height > 0:
                    min_h = min(height_b, l_height)
                    # If vertical overlap is more than 40% of the height of the smaller box, they are on the same line
                    if min_h > 0 and (overlap_height / min_h) > 0.4:
                        line.append(block)
                        placed = True
                        break
            
            if not placed:
                lines.append([block])
                
        # 3. For each line, sort elements by X coordinate and merge them
        merged_blocks = []
        for line in lines:
            line.sort(key=lambda b: b["bbox"][0])
            
            current_block = line[0].copy()
            for next_block in line[1:]:
                c_x1, c_y1, c_x2, c_y2 = current_block["bbox"]
                n_x1, n_y1, n_x2, n_y2 = next_block["bbox"]
                
                c_height = c_y2 - c_y1
                n_height = n_y2 - n_y1
                avg_height = (c_height + n_height) / 2.0
                
                x_gap = n_x1 - c_x2
                
                # Check if close horizontally
                close_horizontally = x_gap < (avg_height * self.max_x_gap_multiplier)
                
                if close_horizontally:
                    # Merge next_block into current_block
                    current_block["text"] += " " + next_block["text"]
                    current_block["bbox"] = [
                        min(c_x1, n_x1),
                        min(c_y1, n_y1),
                        max(c_x2, n_x2),
                        max(c_y2, n_y2)
                    ]
                    current_block["confidence"] = round((current_block["confidence"] + next_block["confidence"]) / 2.0, 3)
                else:
                    merged_blocks.append(current_block)
                    current_block = next_block.copy()
                    
            if current_block:
                merged_blocks.append(current_block)
                
        # 4. Sort merged blocks by Y (top) then X (left) to ensure final reading order is top-to-bottom
        merged_blocks.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
        return merged_blocks
