# Workflow and architecture notes

## Responsibility boundaries

| Layer | Responsibility | Cannot do |
|---|---|---|
| UI | Select a request, show evidence and recommendation | Approve or purchase |
| Evidence tools | Retrieve read-only business facts | Alter source data or execute request text |
| Optional LLM | Synthesize the completed evidence pack | Alter policy, approve, or invoke side effects |
| Policy engine | Apply explicit thresholds, dates, and routing rules | Invent evidence or make a human approval |
| Human reviewers | Accept, reject, or grant an exception | Be replaced by the copilot |

## Stop and escalation rules

The workflow stops for clarification when required details are missing. It escalates to Security when a review is absent, expired, conflicting, unavailable, or the requested data/integration is sensitive. Privacy and Legal are added when policy requires them; Finance is added for budget exceptions. Any instruction-like content embedded in a request is ignored as an instruction and reported as a risk flag.

## Deliberate non-goals

No autonomous purchasing, budget updates, contract acceptance, production authentication, or persistent approval workflow is included. The copilot is a bounded recommendation layer for a human procurement process.
