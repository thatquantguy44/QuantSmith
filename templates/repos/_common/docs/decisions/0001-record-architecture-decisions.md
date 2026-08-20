# 1. Record architecture decisions

- **Status:** accepted
- **Date:** <YYYY-MM-DD>

## Context

Decisions get made in threads and calls, and the reasoning evaporates. Six
months later nobody can say why the boundary is where it is, so it gets
relitigated or, worse, violated by accident.

## Decision

Record each significant architectural decision here as a numbered file:
context, the decision, the alternatives rejected, and the consequences.

An ADR is immutable. Superseding one means writing a new ADR that references
it, never editing the original — the point is the trail, not the conclusion.

## Consequences

- A new owner can reconstruct reasoning without asking anyone.
- Every non-obvious constraint has a citable reason.
- Writing one costs ~20 minutes. Not writing one costs a rediscovery.
