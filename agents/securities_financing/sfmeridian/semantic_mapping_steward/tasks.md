# Semantic Mapping Steward Tasks

## Catalog Refresh and Drift

Input: the SFMeridian configuration and, optionally, injected connections.

Output: catalog snapshots, classified diffs, and the drift list that excludes
affected queries from retrieval.

## Mapping Validation

Input: the `semantic_mapping` bindings and `governed_tier.metric_sources`.

Output: each binding's status with resolved columns and problems, every
governed metric's coverage, and each metric source's availability.

## Pack Amendment Proposals

Input: concepts the mapping or the query repository uses that the `0081` pack lacks.

Output: shipped amendment proposals staged for the named pack reviewer; the
pack file and its review block are unchanged.

## Access Review

Input: the `0058` roster and the configured column classes.

Output: which classed columns' values a caller may see.
