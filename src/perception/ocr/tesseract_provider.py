"""
AMEVA Voice Screen Assistant — Tesseract OCR Provider
=====================================================
Uses pytesseract to extract text and bounding boxes from images.
Requires Tesseract OCR OS-level installation.
"""

import logging
from typing import Any

import pytesseract
from PIL import Image

from src.perception.ocr.postprocessor import OCRPostProcessor

logger = logging.getLogger("ameva.perception.ocr")


class TesseractProvider:
    """Tesseract OCR implementation."""

    def __init__(self, cfg):
        self.cfg = cfg
        tess_cmd = self.cfg.get("ocr", "tesseract_cmd", default="")
        if not tess_cmd:
            import os
            default_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(default_path):
                tess_cmd = default_path
                
        if tess_cmd:
            pytesseract.pytesseract.tesseract_cmd = tess_cmd
        
        self.lang = self.cfg.get("ocr", "lang", default="kor+eng")

    def extract_text_blocks(self, image_path: str) -> dict[str, Any]:
        """Extract text blocks using pytesseract.image_to_data."""
        logger.info(f"Running Tesseract OCR on {image_path}")
        
        try:
            img = Image.open(image_path)
            img_w, img_h = img.size
            data = pytesseract.image_to_data(img, lang=self.lang, output_type=pytesseract.Output.DICT)
            
            blocks = []
            n_boxes = len(data['level'])
            
            for i in range(n_boxes):
                text = data['text'][i].strip()
                # Ignore empty text blocks and low confidence blocks (e.g., < 30)
                conf = float(data['conf'][i])
                if text and conf > 30:
                    x1 = data['left'][i]
                    y1 = data['top'][i]
                    w = data['width'][i]
                    h = data['height'][i]
                    x2 = x1 + w
                    y2 = y1 + h
                    
                    blocks.append({
                        "text": text,
                        "bbox": [x1, y1, x2, y2],
                        "confidence": round(conf / 100.0, 3) # Normalize to 0-1
                    })
                    
            # Post-process the raw blocks
            postprocessor = OCRPostProcessor(min_confidence=0.3)
            processed_blocks = postprocessor.process(blocks)
                    
            return {
                "engine": "tesseract",
                "image_path": str(image_path),
                "resolution": {"width": img_w, "height": img_h},
                "blocks": processed_blocks,
                "raw_blocks": blocks
            }
            
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            raise RuntimeError(f"OCR failed: {e}") from e
