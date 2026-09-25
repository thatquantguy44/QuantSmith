"""Natural-language analytics — spec ``0080-nl-analytics-insights``.

Question -> governed ``QueryPlan`` (``plan.py``) -> interpreted by a pluggable
seam (``interpret.py``) -> checked against viewer clearance (``authorize.py``)
-> executed over injected, read-only rows (``execute.py``) -> charted and
explained -> returned in chat and/or published to a database on request.

This package covers T-001 through T-010 of the spec's task list: plan,
interpret, authorize, execute, chart, insights, narrate, and ``respond.py``'s
``answer()`` entry point. Write-back (``writeback.py``), the ``0070`` audit
envelope, and the two agents follow. Standard library only.
"""
