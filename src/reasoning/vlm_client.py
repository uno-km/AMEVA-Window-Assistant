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
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')

    def generate(self, image_path: str, prompt: str, **kwargs) -> str:
        try:
            base64_image = self._encode_image(image_path)
            
            # Llama.cpp multimodal OpenAI-compatible payload
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
            
            payload = {
                "messages": messages,
                "temperature": kwargs.get("temperature", 0.1),
                "max_tokens": kwargs.get("max_tokens", 512)
            }
            
            req = urllib.request.Request(
                self.endpoint_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            
            with urllib.request.urlopen(req, timeout=120) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
                return resp_data["choices"][0]["message"]["content"].strip()
                
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
    def __init__(self, cfg):
        self.cfg = cfg
        self.provider_name = self.cfg.get("vlm", "provider", default="llama_cpp").lower()
        
        if self.provider_name == "llama_cpp":
            self.adapter = LocalLlamaCppMultimodalAdapter(
                endpoint_url=self.cfg.get("vlm", "endpoint", default="http://127.0.0.1:8081/v1/chat/completions")
            )
        else:
            raise ValueError(f"Unknown VLM provider: {self.provider_name}")
            
    def ask_image(self, image_path: str, prompt: str, **kwargs) -> str:
        """Process an image and text prompt using the configured local VLM."""
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
            
        logger.info(f"VLM reasoning invoked using adapter: {self.adapter.__class__.__name__}")
        return self.adapter.generate(image_path, prompt, **kwargs)
