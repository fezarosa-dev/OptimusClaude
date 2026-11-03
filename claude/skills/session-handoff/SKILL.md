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

## Problems remaining
...

## Decisions
...

## Next step
...

## Suggested memory update
...

Do not claim that a memory or document was updated unless you actually changed it.
