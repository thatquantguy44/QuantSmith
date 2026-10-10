# Bitemporal Data Tasks

## Load A Revised Series

Input: a series with releases and revisions (e.g. advance, second, third estimates).

Output: facts recorded in knowledge-time order with sources, ready for as-of reads.

## Answer As Of A Past Date

Input: keys, a valid time, and a knowledge time.

Output: `as_of` / `snapshot` answers with value, knowledge time, and source.

## Audit A Backtest For Look-Ahead

Input: the facts a backtest used and its decision times.

Output: `lookahead_violations` per decision and the fix (read by knowledge time).

## Explain A Revision

Input: a key and date whose value changed.

Output: the `revisions` trail with each value, knowledge time, and source.
