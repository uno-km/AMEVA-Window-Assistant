"""
AMEVA Voice Screen Assistant — Scene Graph Builder
==================================================
Transforms raw OCR text blocks into a structured scene representation
and a text summary for the reasoning layer.
"""

import json
import logging
from typing import Any

logger = logging.getLogger("ameva.semantic")


class SceneGraphBuilder:
    """Builds semantic understanding from perception output."""

    def __init__(self, cfg):
        self.cfg = cfg

    def build(self, ocr_data: dict[str, Any], user_question: str = "") -> tuple[dict[str, Any], str]:
        """
        Builds the scene graph and text summary.
        
        Returns:
            A tuple of (scene_graph_json, text_summary)
        """
        blocks = ocr_data.get("blocks", [])
        resolution = ocr_data.get("resolution", {"width": 1920, "height": 1080})
        img_w, img_h = resolution["width"], resolution["height"]
        
        # Analyze question relevance
        q = user_question.lower()
        rel_toolbar = any(k in q for k in ["그림", "도구", "버튼", "draw", "tool", "button"])
        rel_sidebar = any(k in q for k in ["파일", "목록", "탐색", "file", "explorer", "sidebar"])
        rel_status = any(k in q for k in ["상태", "메모리", "cpu", "status"])
        # Body is generally always relevant, but highly relevant for logs/text
        
        regions = {
            "toolbar": [],
            "sidebar": [],
            "body": [],
            "status_bar": []
        }
        
        for b in blocks:
            text = b.get("text", "")
            if not text:
                continue
                
            x1, y1, x2, y2 = b.get("bbox")
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            
            # Simple heuristic classification for role
            r_type = "text"
            text_lower = text.lower()
            
            if "error" in text_lower or "exception" in text_lower or "fail" in text_lower:
                r_type = "log"
            elif len(text) < 15 and ("ok" in text_lower or "cancel" in text_lower or "retry" in text_lower or "submit" in text_lower):
                r_type = "button"
            elif len(text) < 30 and text.isupper():
                r_type = "title"
                
            item = {
                "role": r_type,
                "bbox": b.get("bbox"),
                "text": text,
                "confidence": b.get("confidence")
            }
            
            # Layout heuristic
            if cy < img_h * 0.15:
                regions["toolbar"].append(item)
            elif cy > img_h * 0.95:
                regions["status_bar"].append(item)
            elif cx < img_w * 0.25:
                regions["sidebar"].append(item)
            else:
                regions["body"].append(item)

        scene_graph = {
            "screen_type": "unknown_application",
            "resolution": resolution,
            "regions": regions
        }
        
        # Build compressed text summary for prompt
        lines = []
        for region_name, items in regions.items():
            if not items:
                continue
            
            # Relevance compression
            is_relevant = True
            if region_name == "toolbar" and not rel_toolbar and len(items) > 5:
                is_relevant = False
            elif region_name == "sidebar" and not rel_sidebar and len(items) > 5:
                is_relevant = False
            elif region_name == "status_bar" and not rel_status and len(items) > 3:
                is_relevant = False
                
            if is_relevant:
                lines.append(f"--- [REGION: {region_name.upper()}] ---")
                for r in items:
                    lines.append(f"[{r['role'].upper()}] {r['text']}")
            else:
                lines.append(f"--- [REGION: {region_name.upper()}] ({len(items)} items hidden) ---")
            
        summary = "\n".join(lines)
        if not summary:
            summary = "No readable text found on the screen."
            
        return scene_graph, summary
