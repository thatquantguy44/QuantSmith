# Backfill & Reprocessing Tasks

## Plan A Restatement

Input: the restated versions and the lineage graph.

Output: a `plan_reprocessing` plan listing exactly the downstream runs in order.

## Run A Backfill Under Limits

Input: a plan, recompute functions, and fleet pools.

Output: an `execute_plan` run with new versions, lineage, and a manifest.

## Gate And Publish

Input: old and new outputs, keys, and acceptance gates.

Output: diffs per dataset and an all-or-nothing `swap` outcome with rollback pointers.

## Roll Back A Reprocessing

Input: a `SwapOutcome`.

Output: the restored pointers and a record of why.
