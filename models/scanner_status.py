# models/scanner_status.py
import subprocess
import platform
from dataclasses import dataclass
from pathlib import Path

_SCANNER_HINTS = ("scanner", "barcode", "symbol", "zebra", "honeywell", "datalogic")

@dataclass(frozen=True)
class ScannerStatus:
    ok: bool
    message: str
    candidates: list[str]


def detect_scanner() -> ScannerStatus:
    sysname = platform.system().lower()

    if sysname == "linux":
        candidates: list[str] = []

        by_id = Path("/dev/input/by-id")
        if by_id.exists():
            for p in by_id.iterdir():
                name = p.name.lower()
                if any(h in name for h in _SCANNER_HINTS):
                    candidates.append(str(p))

        try:
            out = subprocess.check_output(["lsusb"], text=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                low = line.lower()
                if any(h in low for h in _SCANNER_HINTS):
                    candidates.append(line.strip())
        except Exception:
            pass

        uniq = sorted(set(candidates))
        if uniq:
            return ScannerStatus(True, "Scanner-like device detected (heuristic).", uniq)

        return ScannerStatus(
            False,
            "No obvious scanner detected. Note: HID keyboard-style scanners often can't be reliably detected.",
            [],
        )

    return ScannerStatus(
        False,
        f"Scanner detection not implemented for {platform.system()} (common HID scanners still work).",
        [],
    )