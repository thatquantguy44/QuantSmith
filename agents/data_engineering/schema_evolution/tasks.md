# Schema Evolution Tasks

## Assess A Schema Change

Input: old and new schema versions.

Output: a classified change list with break directions and a verdict against the mode.

## Choose A Compatibility Mode

Input: the producers, consumers, and upgrade order.

Output: `backward`, `forward`, or `full`, with the reasoning and the `check` to enforce it.

## Check A Delivery For Drift

Input: a declared schema and delivered rows.

Output: a `detect_drift` report and a quarantine-or-load decision.

## Plan A Replay Under A New Schema

Input: historical data and the target schema.

Output: an `evolve_rows` plan if backward compatible, otherwise the two-step migration.
