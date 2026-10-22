"""SFMeridian — securities finance intelligence plugin (spec ``0113``).

Grounded answers to securities-lending questions from an adopter's own
databases, learned from a configurable repository of reviewed SQL queries.
This release (spec ``0114``) ships configuration, repository indexing,
search, the reviewed feedback inbox, governance catalogs, the tool registry,
the agent loop harness, and the first loop agent, ``query_librarian``.
"""

__version__ = "0.1.0"
#: Version of the tool contract apps depend on (``0113`` NFR-007, SemVer).
CONTRACT_VERSION = "0.1.0"

__all__ = ["CONTRACT_VERSION", "__version__"]
