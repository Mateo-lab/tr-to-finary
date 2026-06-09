"""Fetch transactions from Trade Republic using pytr."""

import subprocess
import sys
from pathlib import Path

from .utils import get_pytr_path


def fetch_transactions(
    output_dir: Path,
    output_file: str = "tr_transactions.csv",
    last_days: int = 0,
    lang: str = "en",
    phone_no: str | None = None,
    pin: str | None = None,
) -> Path:
    """
    Use pytr to fetch transactions from Trade Republic and export to CSV.

    Args:
        output_dir: Directory where the CSV will be saved.
        output_file: Name of the output CSV file.
        last_days: Only fetch last N days (0 = all).
        lang: Language for CSV columns.
        phone_no: TR phone number (optional if stored).
        pin: TR PIN (optional if stored).

    Returns:
        Path to the exported CSV file.
    """
    output_path = output_dir / output_file

    pytr = get_pytr_path()
    cmd = [
        sys.executable, "-m", "pytr",
        "export_transactions",
        "--export-format", "csv",
        "--sort",
        "--lang", lang,
        "--no-date-with-time",
        "--no-decimal-localization",
        "--outputdir", str(output_dir),
        str(output_path),
    ]

    if last_days > 0:
        cmd.extend(["--last_days", str(last_days)])

    if phone_no:
        cmd.extend(["--phone_no", phone_no])
    if pin:
        cmd.extend(["--pin", pin])

    print(f"Fetching transactions from Trade Republic via pytr...")
    print(f"  Command: {' '.join(cmd[-6:])}")
    print()
    print("  You may need to confirm the login on your Trade Republic app.")
    print()

    try:
        result = subprocess.run(
            cmd,
            cwd=str(output_dir),
            timeout=120,
        )

        if result.returncode != 0:
            raise RuntimeError(f"pytr exited with code {result.returncode}")

        if not output_path.exists():
            # pytr may have written to the default name
            default_path = output_dir / "account_transactions.csv"
            if default_path.exists():
                return default_path
            raise RuntimeError(f"Output file not found: {output_path}")

        return output_path

    except FileNotFoundError:
        raise RuntimeError(
            "pytr is not installed or not found.\n"
            "Run: pip install pytr\n"
            "Then: pytr login  (to set up credentials)"
        )


def ensure_pytr_login(phone_no: str | None = None, pin: str | None = None):
    """Ensure pytr credentials are stored. Interactive."""
    cmd = [sys.executable, "-m", "pytr", "login", "--store_credentials"]
    if phone_no:
        cmd.extend(["--phone_no", phone_no])
    if pin:
        cmd.extend(["--pin", pin])

    print("Setting up Trade Republic login via pytr...")
    subprocess.run(cmd)
