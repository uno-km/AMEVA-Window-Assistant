import pytest
from src.reasoning.vlm_client import LocalLlamaCppMultimodalAdapter

def test_llama_cpp_adapter_no_connection():
    adapter = LocalLlamaCppMultimodalAdapter(endpoint_url="http://localhost:9999/v1/invalid")
    
    # Needs a real file to encode
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        tf.write(b"fake_image_bytes")
        tf_name = tf.name
        
    import os
    try:
        with pytest.raises(ConnectionError):
            adapter.generate(tf_name, "test prompt")
    finally:
        os.unlink(tf_name)
