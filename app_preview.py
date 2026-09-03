"""Explicit local-only design preview; never a deployment entry point."""
from pathlib import Path
from awesome.list_ui import render
render(Path(__file__).resolve().parent, preview=True)
