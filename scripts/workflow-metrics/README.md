# Workflow metrics

Scripts that measure how an agent session spent its tokens and time. They read the transcripts
Claude Code keeps on the developer's machine and print summaries. They write nothing, need only
the Python standard library, and hold no path: the transcript directory is derived from the
project directory at run time.

Run them from the repository root:

```sh
python3 -B scripts/workflow-metrics/usage.py      # tokens and estimated cost by role and model
python3 -B scripts/workflow-metrics/context.py    # context size, limit stops, repeated work
python3 -B scripts/workflow-metrics/reviews.py    # one line per review run, and what reviewers read
python3 -B scripts/workflow-metrics/audit.py      # forbidden accesses in a blind review run
```

Each takes `--project-dir` to measure another checkout or a scratch directory, and `--help`.

## What the numbers are

- **Tokens** come from the usage block of each model request and are counted once per request.
- **Estimated cost** multiplies tokens by the rates in `weights.json`. Those rates were fitted
  to Claude Code's own cost records. Use the estimate to compare one run with another. It is
  not a bill, and it does not say how a subscription counts usage.
- **Sessions and reviews** are printed as `S1`, `S2` and `R1`, `R2` in time order. Session
  identifiers and paths are not printed.

## Limits

- The transcripts are local. A result from these scripts can be reproduced only on the machine
  that holds them, so a figure quoted from them in a document is labelled as local.
- The transcript format belongs to Claude Code and can change between versions. The scripts were
  written against version 2.1.325.
- `audit.py` reports what a run did, after the fact. It does not prevent anything.
- Output may include the description a caller gave a review. Check it for private details
  before pasting it into a public document.
