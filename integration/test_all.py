"""Run both project test suites from the integrated repository root."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_suite(name: str, directory: Path) -> None:
    print(f"\n=== {name} ===", flush=True)
    subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=directory,
        check=True,
    )


if __name__ == "__main__":
    run_suite("Agent + RAG", ROOT / "agent")
    run_suite("IoT monitor + protected API", ROOT / "monitor")
    print("\n=== Cross-project HTTP smoke test ===", flush=True)
    subprocess.run([sys.executable, "integration/test_http_smoke.py"], cwd=ROOT, check=True)
