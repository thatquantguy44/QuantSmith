# Fair Lending Review Tasks

## Disparity Measurement

Input: a scored population, a cutoff, and a disparity threshold.

Output: adverse impact ratio, per-group approval rates, and breach status.

## Proxy Association

Input: a scored population and a named feature.

Output: the feature's correlation with protected-class membership.

## Less-Discriminatory Alternative Search

Input: a scored population whose baseline breaches the threshold, candidate
alternative cutoffs, and a maximum acceptable approval-rate change.

Output: a recommended cutoff, or an honest report that none was found within
tolerance.

## Composed Fairness Review

Input: a scored population, cutoff, disparity threshold, features to test,
and (if needed) LDA search inputs.

Output: the full fairness harness report — disparity, proxy associations,
and, when breached, the alternative-search result.
