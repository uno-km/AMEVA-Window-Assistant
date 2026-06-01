"""
Tests for Phase 2: Scene Graph Builder (Layout Segmentation & Context Compression)
"""

import json
from src.semantic.scene_graph_builder import SceneGraphBuilder

class DummyCfg:
    def get(self, *args, **kwargs):
        return kwargs.get("default", None)

def test_scene_graph_relevance():
    builder = SceneGraphBuilder(DummyCfg())
    
    mock_ocr = {
        "resolution": {"width": 1920, "height": 1080},
        "blocks": [
            # Toolbar area (y < 162)
            {"text": "File", "bbox": [10, 10, 50, 40], "confidence": 0.9},
            {"text": "Edit", "bbox": [60, 10, 100, 40], "confidence": 0.9},
            {"text": "View", "bbox": [110, 10, 150, 40], "confidence": 0.9},
            {"text": "Draw", "bbox": [160, 10, 200, 40], "confidence": 0.9},
            {"text": "Help", "bbox": [210, 10, 250, 40], "confidence": 0.9},
            {"text": "Tools", "bbox": [260, 10, 300, 40], "confidence": 0.9},
            # Sidebar area (x < 480)
            {"text": "Project Explorer", "bbox": [10, 200, 200, 230], "confidence": 0.9},
            {"text": "main.py", "bbox": [20, 240, 100, 260], "confidence": 0.9},
            {"text": "utils.py", "bbox": [20, 270, 100, 290], "confidence": 0.9},
            {"text": "config.py", "bbox": [20, 300, 100, 320], "confidence": 0.9},
            {"text": "app.py", "bbox": [20, 330, 100, 350], "confidence": 0.9},
            {"text": "test.py", "bbox": [20, 360, 100, 380], "confidence": 0.9},
            # Body area (center)
            {"text": "def draw_circle():", "bbox": [500, 500, 700, 530], "confidence": 0.9},
            {"text": "    pass", "bbox": [500, 540, 600, 570], "confidence": 0.9},
            # Status bar area (y > 1026)
            {"text": "Ln 10, Col 5", "bbox": [1500, 1050, 1600, 1070], "confidence": 0.9},
            {"text": "UTF-8", "bbox": [1620, 1050, 1680, 1070], "confidence": 0.9},
            {"text": "Python 3.12", "bbox": [1700, 1050, 1800, 1070], "confidence": 0.9},
            {"text": "Plain Text", "bbox": [1820, 1050, 1900, 1070], "confidence": 0.9},
        ]
    }
    
    # 1. Ask about drawing (should prioritize toolbar and body)
    graph, summary = builder.build(mock_ocr, "그림 그리려면 어떻게 해?")
    
    # Toolbar has 6 items, drawing question should keep them visible
    assert "--- [REGION: TOOLBAR] ---" in summary
    assert "[TEXT] Draw" in summary
    
    # Sidebar has 6 items, drawing question should hide them
    assert "--- [REGION: SIDEBAR] (6 items hidden) ---" in summary
    assert "main.py" not in summary
    
    # Status bar has 4 items, drawing question should hide them
    assert "--- [REGION: STATUS_BAR] (4 items hidden) ---" in summary
    assert "Plain Text" not in summary
    
    # 2. Ask about status/memory (should prioritize status bar)
    graph2, summary2 = builder.build(mock_ocr, "현재 메모리 상태가 어때?")
    
    # Toolbar has 6 items, status question should hide them
    assert "--- [REGION: TOOLBAR] (6 items hidden) ---" in summary2
    
    # Status bar has 4 items, status question should keep them visible
    assert "--- [REGION: STATUS_BAR] ---" in summary2
    assert "[TEXT] Plain Text" in summary2

if __name__ == "__main__":
    test_scene_graph_relevance()
    print("All tests passed!")
