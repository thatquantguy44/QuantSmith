"""QuantSmith runtime package.

The repository keeps agent contracts under ``agents/`` and executable runtime
code under ``src/quantsmith/``.
"""

# Kept in step with ``version`` in pyproject.toml. Read by
# ``hooks/stages/quantsmith-version-check.sh`` so a consuming repository can be
# told when its pin has drifted from the installed package (spec 0047).
__version__ = "0.1.0"

__all__ = ["agentic_code_tools", "quant", "__version__"]
