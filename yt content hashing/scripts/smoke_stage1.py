"""Optional E2E: process latest input with SAFE (faster). Exit 0 on success."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v7_pipeline.cli import main

if __name__ == "__main__":
    # Prefer SAFE for speed during smoke
    raise SystemExit(main(["--profile", "SAFE"]))
