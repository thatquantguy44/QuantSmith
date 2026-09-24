"""Natural-language analytics — spec ``0080-nl-analytics-insights``.

Question -> governed ``QueryPlan`` (``plan.py``) -> interpreted by a pluggable
seam (``interpret.py``) -> checked against viewer clearance (``authorize.py``)
-> executed over injected, read-only rows (``execute.py``) -> charted and
explained -> returned in chat and/or published to a database on request.

This package covers T-001 through T-006 of the spec's task list (plan,
interpret, authorize, execute); ``chart.py``, ``insights.py``, ``narrate.py``,
``respond.py``, and ``writeback.py`` follow. Standard library only.
"""
