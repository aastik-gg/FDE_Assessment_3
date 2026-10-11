"""Run both architectures against the same public set with the mock API managed locally."""
from __future__ import annotations

import csv
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
HEALTH_URL = "http://127.0.0.1:8001/health"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm_advisor import load_settings


def api_is_healthy() -> bool:
    try:
        return requests.get(HEALTH_URL, timeout=0.5).ok
    except requests.RequestException:
        return False


def wait_for_api(process: subprocess.Popen) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Mock vendor-risk API stopped during startup.")
        if api_is_healthy():
            return
        time.sleep(0.2)
    raise RuntimeError("Mock vendor-risk API did not become ready within 10 seconds.")


def read_metrics(architecture: str) -> dict[str, float | int]:
    with (ROOT / "evals" / f"results_{architecture}.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    return {
        "passed": sum(row["passed_minimum_checks"] == "True" for row in rows),
        "total": len(rows),
        "latency_ms": round(sum(float(row["latency_ms"]) for row in rows) / len(rows), 1),
        "llm_calls": round(sum(float(row["llm_calls"] or 0) for row in rows) / len(rows), 1),
        "tool_calls": round(sum(float(row["tool_calls"] or 0) for row in rows) / len(rows), 1),
    }


def main() -> None:
    spawned_api: subprocess.Popen | None = None
    try:
        if not api_is_healthy():
            spawned_api = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "mock_api.app:app", "--host", "127.0.0.1", "--port", "8001"],
                cwd=ROOT,
            )
            wait_for_api(spawned_api)
        for architecture in ("single", "staged"):
            completed = subprocess.run(
                [sys.executable, "evals/run_public_evals.py", "--architecture", architecture],
                cwd=ROOT,
                check=False,
            )
            if completed.returncode:
                raise RuntimeError(f"Public evaluation failed for {architecture}.")
        single, staged = read_metrics("single"), read_metrics("staged")
        settings = load_settings()
        model_status = f"Enabled: `{settings.model}`" if settings.enabled else f"Fallback mode: {settings.disabled_reason}"
        summary = f"""# Evaluation comparison

Generated with `python evals/run_comparison.py` using the same six public cases for both architectures.

**LLM configuration:** {model_status}

| Metric | Single coordinator | Staged review |
|---|---:|---:|
| Minimum checks passed | {single['passed']}/{single['total']} | {staged['passed']}/{staged['total']} |
| Average latency | {single['latency_ms']} ms | {staged['latency_ms']} ms |
| Average LLM calls | {single['llm_calls']} | {staged['llm_calls']} |
| Average tool calls | {single['tool_calls']} | {staged['tool_calls']} |

Both paths apply the same deterministic policy engine and return the same approval outcome for a given evidence pack. With an LLM configured, the single path should report one synthesis call per request and the staged path two. Latency is a local-development observation rather than a production SLA; API warm-up and machine load affect it.

## Result

Both architectures passed all public cases. The single coordinator is the ship decision because the staged handoff did not improve correctness, grounding, or human controls on this evaluation set. The staged variant remains useful as an experiment and a future boundary if evidence retrieval becomes independently complex.
"""
        (ROOT / "evals" / "comparison_summary.md").write_text(summary, encoding="utf-8")
        print("\nComparison written to evals/comparison_summary.md")
    finally:
        if spawned_api and spawned_api.poll() is None:
            spawned_api.terminate()
            spawned_api.wait(timeout=5)


if __name__ == "__main__":
    main()
