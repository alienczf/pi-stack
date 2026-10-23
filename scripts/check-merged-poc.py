#!/usr/bin/env python3
"""Run the same owned native verifier as pi-streams poc verify."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pi-streams"))
from engine.poc import main

if __name__ == "__main__":
    raise SystemExit(main())
