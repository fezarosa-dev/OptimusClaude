---
name: session-handoff
description: Use before ending a long coding session or switching tasks. Records durable project knowledge and creates a concise handoff for the next session without copying unnecessary code or logs.
---

# Session handoff

Before ending the session:

1. Review the current Git status and diff.
2. Identify what was implemented.
3. Identify what was tested.
4. Record unresolved errors.
5. Record important architecture or dependency decisions.
6. Record the exact next step.
7. Avoid copying large logs, full source files, or temporary reasoning.

Update only the relevant project documentation:

- docs/architecture.md for durable architecture decisions;
- docs/current-state.md for current work and next steps;
- docs/decisions/ for important technical decisions.

Then output:

# Handoff

## Objective
...

## Completed
...

## Files changed
...

## Tests executed
...

## What was tried and why it failed
(The most important section: each attempt that did not work, with the root cause, so the next session does not repeat it. Write "nothing failed" if so.)
...

## Current best theory
(For open bugs or questions: what you believe is going on and the evidence for it.)
...

## Problems remaining
...

## Decisions
...

## Next step
(One concrete, executable action: the command to run or the file and change to make.)
...

## Suggested memory update
...

Do not claim that a memory or document was updated unless you actually changed it.
