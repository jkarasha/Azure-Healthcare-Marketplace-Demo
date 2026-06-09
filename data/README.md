# Data

Prior-auth skill data is split by purpose to avoid retrieval/evaluation leakage:

| Directory | Purpose |
|-----------|---------|
| `policies/` | Canonical policy corpus for indexing and retrieval (RAG input only) |
| `cases/` | Ground truth and evaluation cases for benchmarking |
| `samples/` | Committed reference output examples (assessment reports, letters, waypoints) |
| `pdfs/` | Pre-rendered artifacts used by dataset prep and validation flows |

> **Live workflow outputs** go to `.runs/` at the project root — see [`.runs/README.md`](../.runs/README.md).

Guidelines:

- Do not index `cases/` content into the policy retrieval store.
- Keep indexed policy corpus restricted to `policies/`.
- `samples/` outputs are checked in as reference — regenerate by running the prior-auth workflow.
