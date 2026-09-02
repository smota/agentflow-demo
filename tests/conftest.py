"""Keep test scratch contained and initialize it on genuinely fresh checkouts."""
from pathlib import Path
import pytest


def pytest_configure(config):
    root = Path(__file__).resolve().parents[1]
    cache = root / ".cache"
    target = Path(config.option.basetemp or cache / "pytest").resolve()
    if not target.is_relative_to(cache) or target == cache:
        raise pytest.UsageError("Test basetemp must be a child of the project .cache directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    config.option.basetemp = str(target)
