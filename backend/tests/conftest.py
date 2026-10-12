"""Tests use a disposable database and never start the background simulator."""
import os
import tempfile
from pathlib import Path

_runtime = tempfile.TemporaryDirectory(prefix="pravaha-tests-")
os.environ["PRAVAHA_DATABASE_URL"] = f"sqlite:///{Path(_runtime.name) / 'test.db'}"
os.environ["PRAVAHA_START_SIMULATION"] = "0"

