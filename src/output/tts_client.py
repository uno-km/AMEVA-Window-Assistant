"""
AMEVA Voice Screen Assistant — TTS Client
=========================================
Non-blocking text-to-speech using Windows SAPI through PowerShell.
"""

import logging
import subprocess

logger = logging.getLogger("ameva.output")


class WindowsSAPITTS:
    """
    Non-blocking text-to-speech using Windows SAPI through PowerShell.

    Runs in a subprocess so it never blocks the UI or worker thread
    for longer than the subprocess launch time.
    """

    def speak(self, text: str, **kwargs):
        """Speak the given text.  Non-fatal — logs errors but never raises."""
        if not text or not text.strip():
            return

        # Escape single quotes for PowerShell
        safe_text = text.replace("'", "''")
        # Limit length to prevent very long speech
        if len(safe_text) > 2000:
            safe_text = safe_text[:2000]

        ps_cmd = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Speak('{safe_text}')"
        )

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
