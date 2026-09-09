"""Module entrypoint for ``python -m quantsmith.text_intelligence``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
