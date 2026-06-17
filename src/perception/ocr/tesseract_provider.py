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
            paths = [
                r"C:\ameva\AI_Models\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            ]
            for p in paths:
                if os.path.exists(p):
                    tess_cmd = p
                    break
                
        if tess_cmd:
            pytesseract.pytesseract.tesseract_cmd = tess_cmd
        
        self.lang = self.cfg.get("ocr", "lang", default="kor+eng")
        
        # Setup user-writable tessdata directory to bypass admin permission issues
        import os
        import urllib.request
        
        tessdata_dir = r"C:\ameva\models\ocr\tessdata"
        os.makedirs(tessdata_dir, exist_ok=True)
        
        # Set environment variable for Tesseract
        os.environ["TESSDATA_PREFIX"] = tessdata_dir
        
        # Download language data if missing
        langs_to_check = []
        if "eng" in self.lang:
            langs_to_check.append("eng")
        if "kor" in self.lang:
            langs_to_check.append("kor")
            
        for l in langs_to_check:
            traineddata_path = os.path.join(tessdata_dir, f"{l}.traineddata")
            if not os.path.exists(traineddata_path):
                logger.info(f"Downloading {l}.traineddata to {traineddata_path}...")
                url = f"https://github.com/tesseract-ocr/tessdata_fast/raw/main/{l}.traineddata"
                try:
                    urllib.request.urlretrieve(url, traineddata_path)
                    logger.info(f"Successfully downloaded {l}.traineddata")
                except Exception as e:
                    logger.error(f"Failed to download {l}.traineddata: {e}")

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
