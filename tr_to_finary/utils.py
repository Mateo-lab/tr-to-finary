"""Shared utilities."""

import shutil
import sys


def get_pytr_path() -> str:
    """Find the pytr executable."""
    pytr = shutil.which("pytr")
    if pytr:
        return pytr
    return sys.executable  # fallback to python -m pytr
