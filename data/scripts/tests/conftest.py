import shutil
from pathlib import Path

import pytest

FIXTURE_SRC = Path(__file__).parent / "fixtures" / "src"


@pytest.fixture
def src(tmp_path):
    """Copie modifiable du réseau fictif de test."""
    target = tmp_path / "src"
    shutil.copytree(FIXTURE_SRC, target)
    return target
