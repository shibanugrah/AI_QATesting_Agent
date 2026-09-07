"""Compatibility launcher. Old target configs require explicit project migration."""
from qa_engine.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
