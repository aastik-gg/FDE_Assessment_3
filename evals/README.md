# Public evaluation harness

The six public cases are intentionally visible. Use them to test both architectures while you develop.

Run:

```bash
python3 evals/run_comparison.py
```

This one command starts the local mock vendor-risk API when necessary, runs the
same six public cases on both architectures, exports both CSV files, and writes
`comparison_summary.md`. To run one path while `run_local.py` is already
serving the API, use `python3 evals/run_public_evals.py --architecture single`
or replace `single` with `staged`.

The runner:
- calls `src.solution.handle_request(request_id, architecture)`,
- validates the `ProcurementDecision` schema,
- checks a few minimum expectations,
- measures end-to-end latency,
- exports a CSV result file.

## Important limitations

Passing these checks does **not** guarantee a high score. The assessment also considers:
- whether evidence is actually grounded in tool outputs,
- tool/agent boundaries,
- deterministic vs. probabilistic decisions,
- failure handling,
- architecture quality,
- evaluation reasoning,
- hidden cases.

Do not tune your implementation to request IDs. Hidden cases use different records and values.

## Comparison

Use the same case set for both architectures. Your final evaluation should include at least:

| Metric | Single | Staged / 2-agent |
|---|---:|---:|
| Public cases meeting minimum expectations |  |  |
| Avg latency (ms) |  |  |
| Avg LLM calls |  |  |
| Avg tool calls |  |  |
| Policy failures found manually |  |  |

The public runner can measure latency. LLM/tool counts must come from your own telemetry or the optional telemetry field in the output contract.
