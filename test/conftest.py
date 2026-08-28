import os
import sys
from pathlib import Path

import pytest

# Ensure the project root is importable regardless of how pytest is invoked.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Keep any pre-existing environment from leaking into tests.
for key in (
    "FHIR_BASE_URL",
    "MLFLOW_ENABLED",
    "IAM_JWKS_URL",
    "IAM_ISSUER",
):
    os.environ.pop(key, None)


@pytest.fixture
def config():
    from config.config import Config

    return Config(cwd=Path.cwd())
