"""
AMEVA Voice Screen Assistant — STT Engine (Phase 4)
====================================================
Abstraction layer for Speech-to-Text engines.
Currently supports whisper.cpp binary via subprocess.
"""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("ameva.input.stt")


class STTEngine:
    """
    Whisper.cpp based Speech-to-Text engine.
    
    Requires:
        - whisper.cpp executable (main.exe or whisper-cli.exe)
        - A GGML whisper model file (.bin)
    
    Both paths are read from config.json and can be set via Settings UI.
    """

    def __init__(self, cfg):
        self.cfg = cfg

    def is_configured(self) -> bool:
        """Check if STT engine is properly configured with executable and model."""
        exe = self.cfg.get("stt", "whisper_executable", default="")
        model_dir = self.cfg.get("stt", "model_dir", default="")
        model_file = self.cfg.get("stt", "whisper_model", default="")
        
        if not exe or not Path(exe).exists():
            return False
        if not model_file or not model_dir:
            return False
        if not (Path(model_dir) / model_file).exists():
            return False
        return True

    def get_missing_config_message(self) -> str:
        """Return a user-friendly message about what's missing."""
        exe = self.cfg.get("stt", "whisper_executable", default="")
        model_dir = self.cfg.get("stt", "model_dir", default="")
        model_file = self.cfg.get("stt", "whisper_model", default="")
        
        missing = []
        if not exe or not Path(exe).exists():
            missing.append("whisper.cpp 실행 파일 (Settings → 음성 → Whisper 실행파일)")
        if not model_file or not model_dir or not (Path(model_dir) / model_file).exists():
            missing.append("STT 모델 파일 (Settings → 음성 → STT 모델)")
        
        return "마이크를 사용하려면 다음 설정이 필요합니다:\n\n" + "\n".join(f"• {m}" for m in missing)

    def transcribe(self, wav_path: str) -> str:
        """
        Transcribe a WAV file using whisper.cpp.
        
        Parameters
        ----------
        wav_path : str
            Path to the WAV file (16kHz, mono, int16).
        
        Returns
        -------
        str
            Transcribed text.
        
        Raises
        ------
        FileNotFoundError
            If whisper.cpp executable or model is not found.
        RuntimeError
            If whisper.cpp fails.
        """
        exe = self.cfg.get("stt", "whisper_executable", default="")
        model_dir = self.cfg.get("stt", "model_dir", default="")
        model_file = self.cfg.get("stt", "whisper_model", default="")

        if not exe or not Path(exe).exists():
            raise FileNotFoundError(f"whisper.cpp 실행 파일을 찾을 수 없습니다: '{exe}'")
        if not model_file or not model_dir:
            raise FileNotFoundError(f"STT 모델 파일이 설정되지 않았습니다.")
        
        model = str(Path(model_dir) / model_file)
        if not Path(model).exists():
            raise FileNotFoundError(f"STT 모델 파일을 찾을 수 없습니다: '{model}'")

        wav_path = str(wav_path)

        cmd = [
            exe,
            "-m", model,
            "-f", wav_path,
            "-l", "ko",     # Korean language
            "-nt",          # Clean text output (no timestamps)
            "-otxt",        # Output result in a text file
        ]

        logger.info(f"[STT] Running whisper.cpp: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("whisper.cpp timed out (120s)")
        except FileNotFoundError:
            raise FileNotFoundError(f"whisper.cpp 실행 파일을 실행할 수 없습니다: '{exe}'")

        if result.returncode != 0:
            stderr_msg = result.stderr[:500] if result.stderr else "Unknown error"
            raise RuntimeError(f"whisper.cpp failed (rc={result.returncode}): {stderr_msg}")

        # Try to read output from .txt file first (whisper.cpp --output-txt writes this)
        txt_path = Path(wav_path + ".txt")
        if not txt_path.exists():
            txt_path = Path(wav_path).with_suffix(".txt")

        if txt_path.exists():
            text = txt_path.read_text(encoding="utf-8").strip()
            try:
                txt_path.unlink()
            except OSError:
                pass
            if text:
                return self._clean_text(text)

        # Fallback: parse stdout
        text = result.stdout.strip()
        return self._clean_text(text)

    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean up whisper.cpp output text."""
        import re
        # Remove timestamp markers like [00:00:00.000 --> 00:00:05.000]
        text = re.sub(r'\[\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}\]\s*', '', text)
        # Remove leading/trailing whitespace and collapse multiple spaces
        text = re.sub(r'\s+', ' ', text).strip()
        # Remove common whisper hallucination patterns (repeated phrases, music tags)
        text = re.sub(r'\[음악\]|\[Music\]|\(음악\)|\(Music\)', '', text).strip()
        return text


def list_stt_models(model_dir: str) -> list[str]:
    """
    List available whisper GGML model files in the given directory.
    Returns a list of filenames ending with .bin.
    """
    try:
        p = Path(model_dir)
        if p.exists() and p.is_dir():
            return sorted([f.name for f in p.glob("*.bin")])
    except Exception as e:
        logger.warning(f"[STT] Failed to list models in {model_dir}: {e}")
    return []
