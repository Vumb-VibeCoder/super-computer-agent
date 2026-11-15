import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture(autouse=True)
def _out_dir(tmp_path, monkeypatch):
    """Every test writes its images under its own temp dir."""
    monkeypatch.setenv("SCA_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.delenv("SCA_ALLOWED_PROCESSES", raising=False)
    return tmp_path / "out"
