"""
AMEVA Voice Screen Assistant — Strictly Local Multimodal VLM Client
=====================================================================
Client for Vision Language Models (VLM).
Strictly adheres to local/offline only. External APIs, network uploads,
and cloud inference are explicitly prohibited by architecture rules.
"""

import json
import logging
import base64
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

logger = logging.getLogger("ameva.vlm")

class LocalMultimodalAdapter:
    """Base interface for local multimodal adapters."""
    def generate(self, image_path: str, prompt: str, **kwargs) -> str:
        raise NotImplementedError()


class LocalLlamaCppMultimodalAdapter(LocalMultimodalAdapter):
    """
    Adapter for local llama.cpp server running with an mmproj model.
    Sends base64 encoded image directly to localhost.
    """
    def __init__(self, endpoint_url: str = "http://127.0.0.1:8080/v1/chat/completions"):
        self.endpoint_url = endpoint_url
        
    def _encode_image(self, image_path: str) -> str:
        try:
            from PIL import Image
            import io
            with Image.open(image_path) as img:
                max_size = 1024
                if img.width > max_size or img.height > max_size:
                    logger.info(f"[VLM] Resizing image from {img.width}x{img.height} to fit within {max_size}x{max_size}")
                    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                    img_bytes = io.BytesIO()
                    fmt = img.format if img.format else "JPEG"
                    img.save(img_bytes, format=fmt)
                    return base64.b64encode(img_bytes.getvalue()).decode('utf-8')
        except Exception as e:
            logger.warning(f"[VLM] Failed to optimize image: {e}. Falling back to original.")
            
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')

    def generate(self, image_path: str, prompt: str, **kwargs) -> str:
        try:
            base64_image = self._encode_image(image_path)
            # Port-based API branch
            if "8083" in self.endpoint_url:
                # Qwen2-VL natively supports OpenAI Chat API
                req_url = self.endpoint_url
                payload = {
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                                {"type": "text", "text": prompt}
                            ]
                        }
                    ],
                    "temperature": kwargs.get("temperature", 0.1),
                    "max_tokens": kwargs.get("max_tokens", 1024)
                }
            else:
                # Moondream2 uses /completion with strict <image> tagging
                req_url = self.endpoint_url.replace("/v1/chat/completions", "/completion")
                payload = {
                    "prompt": f"<image>\n\nQuestion: {prompt}\n\nAnswer:",
                    "image_data": [{"data": base64_image, "id": 10}],
                    "temperature": kwargs.get("temperature", 0.1),
                    "n_predict": kwargs.get("max_tokens", 512)
                }
            
            req = urllib.request.Request(
                req_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            
            import time
            logger.info(f"[VLM] Sending image analysis request to {req_url}")
            logger.debug(f"[VLM] Payload prompt structure: keys={list(payload.keys())}, base64 length={len(base64_image)} bytes")
            t0 = time.perf_counter()
            
            with urllib.request.urlopen(req, timeout=300) as response:
                latency_ms = int((time.perf_counter() - t0) * 1000)
                raw_body = response.read().decode("utf-8")
                
                logger.info(f"[VLM] Received response in {latency_ms}ms")
                logger.debug(f"[VLM] Raw response: {raw_body}")
                
                resp_data = json.loads(raw_body)
                if "choices" in resp_data:
                    # OpenAI chat completions format
                    if "message" in resp_data["choices"][0]:
                        return resp_data["choices"][0]["message"].get("content", "").strip()
                    # OpenAI completions format (fallback)
                    elif "text" in resp_data["choices"][0]:
                        return resp_data["choices"][0].get("text", "").strip()
                # llama.cpp /completion format
                return resp_data.get("content", "").strip()
                
        except urllib.error.URLError as e:
            logger.error(f"Local VLM connection failed: {e}")
            raise ConnectionError(f"Failed to connect to local VLM: {e}")
        except Exception as e:
            logger.error(f"Local VLM error: {e}")
            raise


class VLMClient:
    """
    High-level client for multimodal reasoning.
    Strictly restricted to load only LocalMultimodalAdapters.
    """
    def __init__(self, cfg, endpoint_url: str = None):
        self.cfg = cfg
        self.provider_name = self.cfg.get("vlm", "provider", default="llama_cpp").lower()
        
        url = endpoint_url or self.cfg.get("vlm", "endpoint", default="http://127.0.0.1:8081/v1/chat/completions")
        
        if self.provider_name == "llama_cpp":
            self.adapter = LocalLlamaCppMultimodalAdapter(
                endpoint_url=url
            )
        else:
            raise ValueError(f"Unknown VLM provider: {self.provider_name}")
            
    def ask_image(self, image_path: str, prompt: str, **kwargs) -> str:
        """Process an image and text prompt using the configured local VLM."""
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
            
        logger.info(f"VLM reasoning invoked using adapter: {self.adapter.__class__.__name__}")
        return self.adapter.generate(image_path, prompt, **kwargs)
