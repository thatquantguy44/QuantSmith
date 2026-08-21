# Macro Regime Classifier Tasks

## Classify The Current Regime

Input: accumulated indicator and policy reads.

Output: a regime label with supporting evidence, an explicit confidence
level, and named change-conditions.

## Assess A Regime Shift

Input: the current classification plus the prior one.

Output: whether the regime has shifted, and specifically which new
evidence drove the change (or didn't).

## Flag Insufficient Evidence

Input: indicator/policy reads too thin to classify confidently.

Output: a stated "not enough evidence to classify" response naming what
additional input would be needed, rather than a forced label.
