---
name: preflight
description: Use before implementing any non-trivial feature, function, bug fix, or refactor. Checks existing project code, native language features, installed libraries, simpler alternatives, and unnecessary complexity before coding.
---

# Preflight: investigate before coding

Before modifying any file, follow these steps.

## Understand the task

Identify:

- the requested behavior;
- expected inputs and outputs;
- files and modules involved;
- project constraints;
- how success will be verified.

If an important requirement is ambiguous, ask questions before coding.

## Search for existing solutions

Check in this order:

1. Existing functions, utilities, components, or services in the project.
2. Native features of the programming language.
3. Libraries already installed.
4. Official framework APIs.
5. A simpler implementation with fewer changes.
6. A new dependency only if necessary.

Use the project's existing code and documentation as evidence.

## Question the implementation

Answer explicitly:

- Does this really need to be implemented?
- Is there a simpler solution?
- Does the language or library already support it?
- Am I creating an abstraction that will only be used once?
- Am I adding a dependency unnecessarily?
- Am I solving a hypothetical problem?
- Does this follow the project's existing patterns?

## Present a plan

Before editing files, show:

- the recommended solution;
- alternatives considered;
- why the recommendation is preferable;
- files that will change;
- tests to run;
- risks and remaining questions.

Do not implement until the plan is clear.

## Implement minimally

When authorized:

- make only the necessary changes;
- reuse existing code;
- avoid unrelated refactors;
- avoid unnecessary abstractions;
- do not add dependencies without justification.

## Final verification

After implementation:

1. Review the diff.
2. Run relevant tests.
3. Run lint and type checks when available.
4. Check error cases and edge cases.
5. Report exactly what changed and what was verified.

Use this format before implementation:

### Understanding
...

### Existing solutions found
...

### Alternatives
...

### Recommended solution
...

### Files to change
...

### Tests planned
...

### Risks and questions
...
