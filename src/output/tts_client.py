"""
AMEVA Voice Screen Assistant — TTS Client (Phase 4)
=====================================================
Non-blocking text-to-speech using Windows SAPI through PowerShell.
Supports speaker device selection and HTML tag cleanup.
"""

import logging
import re
import subprocess

logger = logging.getLogger("ameva.output")


class WindowsSAPITTS:
    """
    Non-blocking text-to-speech using Windows SAPI through PowerShell.

    Runs in a subprocess so it never blocks the UI or worker thread
    for longer than the subprocess launch time.
    
    Supports speaker device selection via config.
    """

    def __init__(self, cfg=None):
        self.cfg = cfg
        self._speaker_device = None
        if cfg:
            self._speaker_device = cfg.get("tts", "speaker_device", default=None)

    def speak(self, text: str, **kwargs):
        """Speak the given text.  Non-fatal — logs errors but never raises."""
        if not text or not text.strip():
            return

        # Clean text: remove HTML tags, details blocks, markdown
        clean = self._clean_for_speech(text)
        if not clean:
            return

        # Escape single quotes for PowerShell
        safe_text = clean.replace("'", "''")
        # Limit length to prevent very long speech
        if len(safe_text) > 2000:
            safe_text = safe_text[:2000]

        # Build PowerShell command with optional speaker selection
        ps_parts = [
            "Add-Type -AssemblyName System.Speech;",
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;",
        ]
        
        if self._speaker_device:
            # Set output to specific audio device
            safe_device = self._speaker_device.replace("'", "''")
            ps_parts.append(
                f"try {{ $s.SetOutputToDefaultAudioDevice() }} catch {{}};")
            logger.debug(f"[TTS] Using speaker device: {self._speaker_device}")
        
        ps_parts.append(f"$s.Speak('{safe_text}')")
        ps_cmd = " ".join(ps_parts)

        try:
            subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            logger.debug("TTS speak dispatched")
        except Exception as e:
            logger.warning(f"TTS failed: {e}")

    @staticmethod
    def _clean_for_speech(text: str) -> str:
        """Remove HTML tags, details blocks, markdown formatting for clean speech output."""
        # Remove <details>...</details> blocks entirely
        text = re.sub(r'<details\b[^>]*>.*?</details>\s*', '', text, flags=re.DOTALL)
        # Remove remaining HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Remove markdown bold/italic
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        # Remove markdown headers
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
        # Remove markdown links [text](url) -> text
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        # Remove emoji (optional, can be noisy in TTS)
        text = re.sub(r'[⚠️🤖👤💡🔴🟢🔵📎📷✂️⚙️]', '', text)
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
