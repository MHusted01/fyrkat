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
python3 -B scripts/workflow-metrics/audit.py --root DIR   # tool calls of a blind review run that may have left it
bash scripts/workflow-metrics/test.sh             # tests for the helpers and the audit
```

Each takes `--project-dir` to measure another checkout or a scratch directory, and `--help`.

## What the numbers are

- **Tokens** come from the usage block of each model request and are counted once per request.
- **Estimated cost** multiplies tokens by the rates in `weights.json`. Those rates were fitted
  to Claude Code's own cost records. Use the estimate to compare one run with another. It is
  not a bill, and it does not say how a subscription counts usage.
- **Sessions and reviews** are printed as `S1`, `S2` and `R1`, `R2` in the order they started.
  The scripts do not print session identifiers, and they replace the home directory in anything
  they quote.
- **Repeats** are identical Read calls and identical commands. A file read through the shell is
  not counted as a read, and most reviewer reading goes through the shell.

## Limits

- The transcripts are local. A result from these scripts can be reproduced only on the machine
  that holds them, so a figure quoted from them in a document is labelled as local.
- The transcript format belongs to Claude Code and can change between versions. The scripts were
  written with version 2.1.325 against transcripts from versions 2.1.319 to 2.1.325.
- Token totals come out about 4% below Claude Code's own cost records, because background
  requests are not in the transcripts.
- Which files a shell command changed, and what a review read, are worked out from command text.
  Both are approximate.
- `audit.py` reads the text of a run's tool calls after the fact and flags any that may have
  reached outside the run. It prefers a false alarm to a miss, so its flags are for reading, not a
  verdict, and each is read by a person or an agent. It checks a reviewer that was told the rules,
  not one that tries to evade them: a path or a program name built at run time is not caught. It
  quotes the start of each flagged command, with the home directory and session identifiers
  replaced, so read its output before pasting it anywhere public.
- Output may include the description a caller gave a review. Check it for private details
  before pasting it into a public document.
