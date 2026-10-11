# Architecture decision memo

## Decision

Ship the **single coordinator** for the MVP.

## Evidence

The same six supplied public cases were run against the single coordinator and staged review path using `python3 evals/run_comparison.py`. Both passed all six minimum checks. Both made six read-only tool calls per request. With a provider configured, the single path makes one advisory LLM call and the staged path makes two; no LLM call can alter a threshold or approval. The decision quality is identical because both architectures use the same deterministic policy engine and receive the same evidence: requester/budget, catalog, vendor registry, vendor-risk API, and written policy.

| Metric | Single coordinator | Staged review |
|---|---:|---:|
| Public cases passing minimum checks | 6/6 | 6/6 |
| Average LLM calls with configured provider | 1.0 | 2.0 |
| Average tool calls | 6.0 | 6.0 |
| Policy / grounding failures | 0 | 0 |

The case set exercises thresholds, existing-tool overlap, source-code access, budget shortfall, new and sensitive vendors, missing fields, embedded prompt injection, and unavailable vendor-risk evidence. Every output preserved human review and did not infer a favorable status when evidence was missing.

## Trade-offs

The staged variant gives a clean `EvidenceAnalyst -> PolicyReviewer` boundary. That may be valuable later if specialist retrieval grows independently or the evidence pack needs separate review. In this MVP, it adds another component to test and observe without adding a tool, a control, a stronger recommendation, or a lower-risk outcome. Local latency is close and not used as a production claim; it is affected by API warm-up and machine load.

## Risks and limitations

Before production, validate role-based access, data redaction, audit retention, real vendor-service failure handling, policy ownership, and a manual evidence-reconciliation workflow. The LLM synthesis remains non-authoritative, is supplied only the evidence pack, and is regression-tested against the deterministic result.

## Why this is the right MVP

The user needs reliable next actions under procurement controls, not unnecessary orchestration. A single coordinator with bounded read-only tools and deterministic policy checks is smaller, easier to audit, and performs as well as the staged alternative on the same test set. Human reviewers continue to approve every purchase and exception.
