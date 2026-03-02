from __future__ import annotations

from pathlib import Path
import sys

if __package__ in (None, ""):
    SCRIPT_DIR = Path(__file__).resolve().parent
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    from _run_model import main_for_model
else:  # pragma: no cover
    from ._run_model import main_for_model


def main() -> int:
    return main_for_model("BilashVIP", "BilashVIP.json")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
