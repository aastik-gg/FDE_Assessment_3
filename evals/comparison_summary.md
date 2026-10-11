# Evaluation comparison

Generated with `python evals/run_comparison.py` using the same six public cases for both architectures.

**LLM configuration:** Fallback mode: MODEL_NAME is not configured; deterministic fallback is active.

| Metric | Single coordinator | Staged review |
|---|---:|---:|
| Minimum checks passed | 6/6 | 6/6 |
| Average latency | 7.1 ms | 8.0 ms |
| Average LLM calls | 0.0 | 0.0 |
| Average tool calls | 6.0 | 6.0 |

Both paths apply the same deterministic policy engine and return the same approval outcome for a given evidence pack. With an LLM configured, the single path should report one synthesis call per request and the staged path two. Latency is a local-development observation rather than a production SLA; API warm-up and machine load affect it.

## Result

Both architectures passed all public cases. The single coordinator is the ship decision because the staged handoff did not improve correctness, grounding, or human controls on this evaluation set. The staged variant remains useful as an experiment and a future boundary if evidence retrieval becomes independently complex.
