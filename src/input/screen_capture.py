"""
AMEVA Voice Screen Assistant — Screen Capture Module
=====================================================
Supports full-screen and per-monitor capture using ``mss`` (preferred)
with ``PIL.ImageGrab`` as fallback.

Captures are saved under ``data/captures/YYYYMMDD/cap_YYYYmmdd_HHMMSS_mmm.png``.
"""

import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("ameva.capture")


class ScreenCapture:
    """
    Screen capture handler.

    Parameters
    ----------
    cfg : AppConfig
        Runtime configuration (reads ``capture.root_dir``, ``capture.mode``, etc.)
    """

    def __init__(self, cfg):
        self.cfg = cfg

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def capture(self, mode: str = None, monitor_index: int = None) -> str:
        """
        Capture the screen and return the absolute file path.

        Parameters
        ----------
        mode : str, optional
            ``"full"`` or ``"monitor"``.  Defaults to config value.
        monitor_index : int, optional
            Monitor index (0-based) when ``mode="monitor"``.
        """
        mode = mode or self.cfg.get("capture", "mode", default="full")
        monitor_index = (
            monitor_index
            if monitor_index is not None
            else self.cfg.get("capture", "monitor_index", default=0)
        )

        out_path = self._make_output_path()

        if mode == "monitor":
            self._capture_monitor(monitor_index, out_path)
        else:
            self._capture_full(out_path)

        logger.info(f"Captured: {out_path}")
        return str(out_path)

    def list_monitors(self) -> list[dict]:
        """Return available monitors as a list of dicts with geometry info."""
        try:
            import mss

            with mss.mss() as sct:
                monitors = []
                # sct.monitors[0] is the virtual combined screen
                for i, m in enumerate(sct.monitors[1:], start=1):
                    monitors.append({
                        "index": i,
                        "left": m["left"],
                        "top": m["top"],
                        "width": m["width"],
                        "height": m["height"],
                    })
                return monitors
        except ImportError:
            logger.warning("mss not installed — monitor listing unavailable")
            return []

    # ------------------------------------------------------------------
    # Internal capture methods
    # ------------------------------------------------------------------
    def _capture_full(self, out_path: Path):
        """Full virtual-screen capture."""
        try:
            import mss
            import mss.tools

            with mss.mss() as sct:
                # monitors[0] = all monitors combined
                shot = sct.grab(sct.monitors[0])
                img = self._mss_to_pil(shot)
                img.save(str(out_path), "PNG")
                return
        except ImportError:
            pass

        # Fallback: Pillow ImageGrab
        from PIL import ImageGrab

        img = ImageGrab.grab(all_screens=True)
        img.save(str(out_path), "PNG")

    def _capture_monitor(self, index: int, out_path: Path):
        """Capture a specific monitor by index."""
        try:
            import mss

            with mss.mss() as sct:
                # index 1-based in mss (0 = virtual combined)
                real_index = index + 1
                if real_index >= len(sct.monitors):
                    logger.warning(
                        f"Monitor index {index} not found, falling back to full screen"
                    )
                    self._capture_full(out_path)
                    return
                shot = sct.grab(sct.monitors[real_index])
                img = self._mss_to_pil(shot)
                img.save(str(out_path), "PNG")
                return
        except ImportError:
            pass

        # Fallback: full screen
        logger.warning("mss not available — using full screen fallback")
        self._capture_full(out_path)

    @staticmethod
    def _mss_to_pil(shot):
        """Convert mss ScreenShot to PIL Image."""
        from PIL import Image

        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------
    def _make_output_path(self) -> Path:
        """Generate the output file path following the naming convention."""
        now = datetime.now()
        root = self.cfg.resolve_path(
            self.cfg.get("capture", "root_dir", default="data/captures")
        )
        day_dir = root / now.strftime("%Y%m%d")
        day_dir.mkdir(parents=True, exist_ok=True)

        filename = now.strftime("cap_%Y%m%d_%H%M%S_") + f"{now.microsecond // 1000:03d}.png"
        return day_dir / filename
