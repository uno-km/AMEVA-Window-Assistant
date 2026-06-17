"""
AMEVA Voice Screen Assistant — Server Manager
=====================================================
Centralized manager for local llama.cpp server processes.
Handles dynamic spawning, checking, and terminating of servers.
"""

import os
import subprocess
import time
import urllib.request
import logging
from src.config import CFG

logger = logging.getLogger("ameva.orchestration.server_manager")

class ServerManager:
    def __init__(self, mode: str = "speed"):
        """
        mode: "speed" (preload all) or "performance" (on-demand loading)
        """
        self.mode = mode
        self.processes = {}  # name -> subprocess.Popen
        self.hw_mode, self.gpu_layers = self._detect_hardware()

    def _detect_hardware(self):
        # Try nvidia-smi first
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            if res.returncode == 0:
                lines = [line.strip() for line in res.stdout.strip().split("\n") if line.strip()]
                if lines:
                    parts = lines[0].split(",")
                    gpu_name = parts[0].strip()
                    gpu_memory = int(parts[1].strip())
                    logger.info(f"[GPU DETECTION] Detected GPU: {gpu_name} (VRAM: {gpu_memory}MB)")
                    return "gpu", 99
        except Exception:
            pass

        # Try GPUtil
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            if len(gpus) > 0:
                logger.info(f"[GPU DETECTION] Detected GPU via GPUtil: {gpus[0].name} (VRAM: {gpus[0].memoryTotal}MB)")
                return "gpu", 99
        except Exception:
            pass

        logger.info("[GPU DETECTION] No GPU detected or check failed. Using CPU mode.")
        return "cpu", 0

    def get_server_config(self, name: str):
        """
        Returns (port, model_path, extra_args_list) for the given server name.
        """
        llama_server_exe = CFG.get("llm", "llama_server_executable", default="C:/ameva/AI_Models/llama.cpp/llama-server.exe")
        
        if name == "llm-server":
            port = 8780
            if self.mode == "performance":
                # Check for 8B model first
                model_8b = "C:/ameva/models/llm/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"
                if os.path.exists(model_8b):
                    model_path = model_8b
                else:
                    model_path = "C:/ameva/models/llm/qwen2.5-3b-instruct-q4_k_m.gguf" if self.hw_mode == "gpu" else "C:/ameva/models/llm/qwen2.5-1.5b-instruct-q4_k_m.gguf"
            else:
                model_path = "C:/ameva/models/llm/qwen2.5-3b-instruct-q4_k_m.gguf" if self.hw_mode == "gpu" else "C:/ameva/models/llm/qwen2.5-1.5b-instruct-q4_k_m.gguf"
            extra = ["--ctx-size", "8192"]

        elif name == "router-server":
            port = 8782
            model_path = "C:/ameva/models/llm/qwen2.5-0.5b-instruct-q4_k_m.gguf"
            extra = ["--ctx-size", "2048"]

        elif name == "vlm-server":
            port = 8783
            model_size = CFG.get("vlm", "model_size", default="2b")
            model_7b = "C:/ameva/models/vlm/Qwen_Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf"
            mmproj_7b = "C:/ameva/models/vlm/mmproj-Qwen_Qwen2.5-VL-7B-Instruct-f16.gguf"
            if model_size == "7b" and os.path.exists(model_7b) and os.path.exists(mmproj_7b):
                model_path = model_7b
                extra = ["--ctx-size", "4096", "--mmproj", mmproj_7b]
            else:
                model_path = "C:/ameva/models/vlm/qwen2-vl-2b-instruct-q4_k_m.gguf"
                extra = ["--ctx-size", "4096", "--mmproj", "C:/ameva/models/vlm/mmproj-Qwen2-VL-2B-Instruct-f16.gguf"]
        else:
            raise ValueError(f"Unknown server: {name}")

        return port, model_path, extra

    def is_alive(self, port: int) -> bool:
        try:
            url = f"http://127.0.0.1:{port}/models"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def start_server(self, name: str, wait_timeout: int = 45) -> bool:
        port, model_path, extra = self.get_server_config(name)
        
        if self.is_alive(port):
            logger.info(f"Server '{name}' on port {port} is already running.")
            return True

        llama_server_exe = CFG.get("llm", "llama_server_executable", default="C:/ameva/AI_Models/llama.cpp/llama-server.exe")
        if not os.path.exists(llama_server_exe):
            logger.error(f"Native llama-server executable not found at: {llama_server_exe}")
            return False

        if not os.path.exists(model_path):
            logger.error(f"Model file not found: {model_path}")
            return False

        cmd = [
            llama_server_exe,
            "--model", model_path,
            "--host", "0.0.0.0",
            "--port", str(port),
            "--n-gpu-layers", str(self.gpu_layers)
        ] + extra

        logger.info(f"[ServerManager] Spawning server '{name}' on port {port} using {os.path.basename(model_path)}")
        logger.debug(f"[ServerManager] Command: {' '.join(cmd)}")

        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        try:
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            proc = subprocess.Popen(
                cmd,
                startupinfo=startupinfo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env
            )
            self.processes[name] = proc
            
            # Wait for port to become responsive
            t0 = time.time()
            while time.time() - t0 < wait_timeout:
                if self.is_alive(port):
                    logger.info(f"Server '{name}' successfully started in {int(time.time() - t0)}s")
                    return True
                time.sleep(1.0)
            
            logger.error(f"Server '{name}' failed to respond within {wait_timeout}s")
            return False
        except Exception as e:
            logger.error(f"Exception while starting '{name}': {e}")
            return False

    def stop_server(self, name: str):
        proc = self.processes.pop(name, None)
        port, _, _ = self.get_server_config(name)
        if proc:
            logger.info(f"[ServerManager] Stopping server '{name}'")
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        else:
            # Fallback: kill process using the port on Windows
            if os.name == 'nt':
                try:
                    # Find PID of process listening on the port
                    out = subprocess.check_output(f'netstat -ano | findstr LISTENING | findstr :{port}', shell=True, text=True)
                    for line in out.strip().split('\n'):
                        parts = line.strip().split()
                        if parts and parts[1].endswith(f":{port}"):
                            pid = parts[-1]
                            logger.info(f"[ServerManager] Killing PID {pid} listening on port {port}")
                            subprocess.run(f'taskkill /F /PID {pid}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass

    def stop_all(self):
        for name in list(self.processes.keys()):
            self.stop_server(name)
        
        # Ensure ports are cleared
        for name in ["llm-server", "router-server", "vlm-server"]:
            try:
                port, _, _ = self.get_server_config(name)
                if self.is_alive(port):
                    self.stop_server(name)
            except Exception:
                pass
