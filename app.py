"""AwesomeAwesomeness: a read-only, versioned directory of Awesome lists."""
from pathlib import Path
from awesome.list_ui import render

render(Path(__file__).resolve().parent)
