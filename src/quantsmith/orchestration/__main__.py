"""Module entry point for ``python -m quantsmith.orchestration``."""

from .replay_cli import main


if __name__ == "__main__":
    raise SystemExit(main())
