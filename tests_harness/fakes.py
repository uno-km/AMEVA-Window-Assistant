"""
AMEVA Test Harness — Fake STT & TTS Providers
===============================================
Drop-in replacements for WhisperCppSTT and WindowsSAPITTS that require
no external binaries or audio hardware.
"""

import logging
import time

logger = logging.getLogger("ameva.fakes")


class FakeWhisperSTT:
    """
    Stub STT that returns a canned response.

    Parameters
    ----------
    response : str
        Fixed text to return for any transcription request.
    delay : float
        Simulated processing time in seconds.
    fail : bool
        If True, raises RuntimeError to test error paths.
    """

    def __init__(self, response: str = "테스트 음성 입력입니다.", delay: float = 0.3, fail: bool = False):
        self.response = response
        self.delay = delay
        self.fail = fail

    def transcribe(self, wav_path: str = None) -> str:
        time.sleep(self.delay)
        if self.fail:
            raise RuntimeError("FakeWhisperSTT: forced failure for testing")
        logger.info(f"FakeWhisperSTT returning: '{self.response}'")
        return self.response


class FakeTTS:
    """
    Stub TTS that logs speak calls without producing audio.
    """

    def __init__(self):
        self.history: list[str] = []

    def speak(self, text: str, **kwargs):
        self.history.append(text)
        logger.info(f"FakeTTS.speak: '{text[:60]}...'")
