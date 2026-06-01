"""
AMEVA Voice Screen Assistant — Audio Input (Phase 4)
=====================================================
Real-time microphone recording with silence detection using sounddevice.
Supports device selection and configurable silence timeout.
"""

import logging
import numpy as np
import queue
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("ameva.input.audio")

# ---------------------------------------------------------------------------
# Device enumeration
# ---------------------------------------------------------------------------

def list_audio_devices() -> dict:
    """
    Return available input (microphone) and output (speaker) devices.
    
    Returns dict with keys 'input' and 'output', each a list of
    {'index': int, 'name': str, 'channels': int}.
    """
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        result = {"input": [], "output": []}
        for i, d in enumerate(devices):
            entry = {"index": i, "name": d["name"], "channels_in": d["max_input_channels"], "channels_out": d["max_output_channels"]}
            if d["max_input_channels"] > 0:
                result["input"].append(entry)
            if d["max_output_channels"] > 0:
                result["output"].append(entry)
        return result
    except Exception as e:
        logger.warning(f"Failed to enumerate audio devices: {e}")
        return {"input": [], "output": []}


# ---------------------------------------------------------------------------
# MicRecorder — real-time recording with silence detection
# ---------------------------------------------------------------------------

class MicRecorder:
    """
    Records audio from a microphone with real-time silence detection.
    
    Usage:
        recorder = MicRecorder(cfg, on_complete=callback)
        recorder.start(silence_timeout=5)
        # ... recording happens in background ...
        # callback(wav_path) is called when silence is detected or stop() is called
        recorder.stop()  # manual stop
    """

    def __init__(self, cfg, on_complete: Callable[[str], None] = None):
        self.cfg = cfg
        self.on_complete = on_complete
        
        self._sample_rate = 16000
        self._channels = 1
        self._dtype = "int16"
        
        self._is_recording = False
        self._stream = None
        self._audio_chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        
        # Silence detection
        self._silence_timeout = 5.0  # seconds
        self._silence_threshold = cfg.get("stt", "silence_threshold_rms", default=500)
        self._last_sound_time = 0.0
        self._has_heard_speech = False

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def start(self, silence_timeout: float = 5.0, device_index: int = None):
        """Start recording from the microphone."""
        if self._is_recording:
            logger.warning("[MicRecorder] Already recording, ignoring start()")
            return

        try:
            import sounddevice as sd
        except ImportError:
            raise RuntimeError("sounddevice not installed. Run: pip install sounddevice")

        self._silence_timeout = silence_timeout
        self._audio_chunks = []
        self._has_heard_speech = False
        self._last_sound_time = time.time()
        self._is_recording = True

        # Resolve device
        if device_index is None:
            device_index = self.cfg.get("stt", "mic_device_index", default=None)

        logger.info(f"[MicRecorder] Starting recording (device={device_index}, silence_timeout={silence_timeout}s, threshold={self._silence_threshold})")

        try:
            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype=self._dtype,
                device=device_index,
                blocksize=int(self._sample_rate * 0.1),  # 100ms blocks
                callback=self._audio_callback,
            )
            self._stream.start()
        except Exception as e:
            self._is_recording = False
            logger.error(f"[MicRecorder] Failed to start stream: {e}")
            raise

        # Start silence monitor thread
        self._monitor_thread = threading.Thread(target=self._monitor_silence, daemon=True)
        self._monitor_thread.start()

    def stop(self) -> Optional[str]:
        """
        Stop recording and save the audio to a WAV file.
        Returns the WAV file path, or None if no audio was captured.
        """
        if not self._is_recording:
            return None

        self._is_recording = False
        
        try:
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
                self._stream = None
        except Exception as e:
            logger.warning(f"[MicRecorder] Error stopping stream: {e}")

        with self._lock:
            if not self._audio_chunks:
                logger.info("[MicRecorder] No audio captured")
                return None

            audio_data = np.concatenate(self._audio_chunks, axis=0)
            self._audio_chunks = []

        # Check if we have meaningful audio (at least 0.5 seconds)
        min_samples = int(self._sample_rate * 0.5)
        if len(audio_data) < min_samples:
            logger.info("[MicRecorder] Audio too short, discarding")
            return None

        # Save WAV
        wav_path = self._save_wav(audio_data)
        logger.info(f"[MicRecorder] Saved recording: {wav_path} ({len(audio_data) / self._sample_rate:.1f}s)")
        return wav_path

    def _audio_callback(self, indata, frames, time_info, status):
        """Called by sounddevice for each audio block."""
        if status:
            logger.debug(f"[MicRecorder] Stream status: {status}")

        if not self._is_recording:
            return

        audio_block = indata.copy()
        
        with self._lock:
            self._audio_chunks.append(audio_block)

        # RMS energy check for silence detection
        rms = np.sqrt(np.mean(audio_block.astype(np.float32) ** 2))
        
        if rms > self._silence_threshold:
            self._last_sound_time = time.time()
            if not self._has_heard_speech:
                self._has_heard_speech = True
                logger.debug("[MicRecorder] Speech detected")

    def _monitor_silence(self):
        """Background thread that monitors for silence timeout."""
        while self._is_recording:
            time.sleep(0.2)
            
            if not self._has_heard_speech:
                # Haven't heard any speech yet — don't timeout
                continue

            elapsed_silence = time.time() - self._last_sound_time
            if elapsed_silence >= self._silence_timeout:
                logger.info(f"[MicRecorder] Silence detected ({elapsed_silence:.1f}s >= {self._silence_timeout}s). Stopping.")
                wav_path = self.stop()
                if self.on_complete and wav_path:
                    self.on_complete(wav_path)
                return

    def _save_wav(self, audio_data: np.ndarray) -> str:
        """Save audio data to a WAV file and return the path."""
        try:
            import soundfile as sf
        except ImportError:
            raise RuntimeError("soundfile not installed. Run: pip install soundfile")

        # Save to persistent data directory
        data_dir = Path("C:/ameva/AMEVA-Window-Assistant/data/audio")
        data_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        wav_path = data_dir / f"rec_{ts}.wav"

        sf.write(str(wav_path), audio_data, self._sample_rate)
        return str(wav_path)


# ---------------------------------------------------------------------------
# Legacy WhisperCppSTT (kept for backward compatibility)
# ---------------------------------------------------------------------------

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
        import subprocess
        
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
            alt = Path(wav_path).with_suffix(".txt")
            if alt.exists():
                txt_path = alt

        if txt_path.exists():
            text = txt_path.read_text(encoding="utf-8").strip()
            try:
                txt_path.unlink()
            except OSError:
                pass
            return text

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

        # Save to persistent data directory
        data_dir = Path("C:/ameva/AMEVA-Window-Assistant/data/audio")
        data_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        wav_path = data_dir / f"rec_{ts}.wav"

        sf.write(str(wav_path), audio, sample_rate)
        logger.info(f"Recorded: {wav_path}")
        return str(wav_path)
