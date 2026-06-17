"""
AMEVA Voice Screen Assistant — Exception Guard
===============================================
Decorator that wraps critical functions to prevent uncaught crashes.
Errors are logged to both the Python logger and the SQLite ``tb_log`` table.
"""

import functools
import logging
import traceback

logger = logging.getLogger("ameva")

# ---------------------------------------------------------------------------
# Late-bound database reference
# ---------------------------------------------------------------------------
# We avoid a circular import by storing a reference that ``run.py`` sets
# after the database is initialized.
_db_ref = None


def set_db_ref(db):
    """Called once at startup to bind the database manager for error logging."""
    global _db_ref
    _db_ref = db


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------
def exception_guard(location: str = None, reraise: bool = False):
    """
    Wrap a function so that any unhandled exception is caught, logged, and
    optionally re-raised.

    Parameters
    ----------
    location : str, optional
        Human-readable label for the error origin (e.g. ``"worker.run"``).
        Defaults to the decorated function's qualified name.
    reraise : bool
        If ``True``, the exception is re-raised after logging.

    Example
    -------
    ::

        @exception_guard(location="capture.full_screen")
        def capture_full():
            ...
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            loc = location or f"{func.__qualname__}()"
            try:
                return func(*args, **kwargs)
            except Exception as e:
                tb_str = traceback.format_exc()
                msg = f"[{loc}] {type(e).__name__}: {e}"
                logger.error(msg, exc_info=True)

                # Attempt to persist to database
                if _db_ref is not None:
                    try:
                        _db_ref.insert_log(
                            task_id=None,
                            level="ERROR",
                            message=msg,
                            tb=tb_str,
                        )
                    except Exception:
                        logger.warning(
                            "Failed to write error to tb_log", exc_info=True
                        )

                if reraise:
                    raise
                return None

        return wrapper

    return decorator
