"""
AMEVA Voice Screen Assistant — Audio Input
==========================================
Offline speech-to-text using a whisper.cpp binary.
"""

import logging
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("ameva.input")


class WhisperCppSTT:
    """
    Offline speech-to-text using a whisper.cpp binary.

    Flow: record mic → save WAV → run whisper.cpp → parse output text.
    """

    def __init__(self, cfg):
        self.cfg = cfg
        self.executable = cfg.get("stt", "whisper_executable", default="")
        self.model_path = cfg.get("stt", "whisper_model", default="")
        self.max_sec = cfg.get("stt", "recording_max_sec", default=30)

    def transcribe(self, wav_path: str = None) -> str:
        """
        Record (if no wav_path given) then transcribe.

        Returns the recognised text or raises on failure.
        """
        if not wav_path:
            wav_path = self._record()

        if not self.executable or not Path(self.executable).exists():
            raise FileNotFoundError(
                f"whisper.cpp executable not found: '{self.executable}'"
            )
        if not self.model_path or not Path(self.model_path).exists():
            raise FileNotFoundError(
                f"whisper model not found: '{self.model_path}'"
            )

        wav_path = str(wav_path)
        out_txt = wav_path + ".txt"

        cmd = [
            self.executable,
            "-m", str(self.model_path),
            "-f", wav_path,
            "--output-txt",
            "--no-prints",
        ]

        logger.info(f"Running whisper.cpp: {' '.join(cmd)}")
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"whisper.cpp failed (rc={result.returncode}): {result.stderr[:500]}"
            )

        # whisper.cpp writes {input}.txt
        txt_path = Path(out_txt)
        if not txt_path.exists():
            # Try without extension doubling
            alt = Path(wav_path).with_suffix(".txt")
            if alt.exists():
                txt_path = alt

        if txt_path.exists():
            text = txt_path.read_text(encoding="utf-8").strip()
            # Cleanup temp files
            try:
                txt_path.unlink()
            except OSError:
                pass
            return text

        # Fallback: parse stdout
        return result.stdout.strip()

    def _record(self) -> str:
        """Record from the default microphone and return the WAV path."""
        try:
            import sounddevice as sd
            import soundfile as sf
        except ImportError:
            raise RuntimeError(
                "sounddevice / soundfile not installed.  "
                "Run: pip install sounddevice soundfile"
            )

        sample_rate = 16000
        duration = min(self.max_sec, 30)

        logger.info(f"Recording for up to {duration}s at {sample_rate}Hz")
        audio = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
        )
        sd.wait()

        tmp_dir = Path(tempfile.gettempdir()) / "ameva_stt"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        wav_path = tmp_dir / f"rec_{ts}.wav"

        sf.write(str(wav_path), audio, sample_rate)
        logger.info(f"Recorded: {wav_path}")
        return str(wav_path)
